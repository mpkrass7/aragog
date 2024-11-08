# Copyright 2024 DataRobot, Inc. and its affiliates.
# All rights reserved.
# DataRobot, Inc.
# This is proprietary source code of DataRobot, Inc. and its
# affiliates.
# Released under the terms of DataRobot Tool and Utility Agreement.


import json
import os

from langchain.chains import (
    create_history_aware_retriever,
    create_retrieval_chain,
)
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.callbacks import get_openai_callback
from langchain_community.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddings,
)
from langchain_community.vectorstores.faiss import FAISS
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import AzureChatOpenAI
from pandas import DataFrame  # type: ignore


def get_chain(input_dir, **params):
    """Instantiate the RAG chain."""
    embedding_function = SentenceTransformerEmbeddings(
        model_name=params["embedding_model_name"],
        cache_folder=input_dir + "/sentencetransformers",
    )
    db = FAISS.load_local(
        folder_path=input_dir + "/faiss_db",
        embeddings=embedding_function,
        allow_dangerous_deserialization=True,
    )
    llm = AzureChatOpenAI(
        deployment_name=params["openai_deployment_name"],
        azure_endpoint=params["azure_endpoint"],
        openai_api_version=params["openai_api_version"],
        openai_api_key=params["openai_api_key"],
        model_name=params["openai_deployment_name"],
        temperature=params["temperature"],
        verbose=True,
        max_retries=params["max_retries"],
        request_timeout=params["request_timeout"],
    )
    retriever = VectorStoreRetriever(
        vectorstore=db,
    )
    system_template = params["stuff_prompt"]
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, just "
        "reformulate it if needed and otherwise return it as is."
    )
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    # Answer question
    qa_system_prompt = system_template
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    # Below we use create_stuff_documents_chain to feed all retrieved context
    # into the LLM. Note that we can also use StuffDocumentsChain and other
    # instances of BaseCombineDocumentsChain.
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    return rag_chain


def load_model(input_dir):
    """Load vector database and prepare chain."""

    from datarobot_drum import RuntimeParameters  # type: ignore

    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    params = {}
    try:
        params["embedding_model_name"] = RuntimeParameters.get("embedding_model_name")
        params["azure_endpoint"] = RuntimeParameters.get("azure_endpoint")
        params["openai_api_version"] = RuntimeParameters.get("openai_api_version")
        params["openai_deployment_name"] = RuntimeParameters.get(
            "openai_deployment_name"
        )
        params["temperature"] = RuntimeParameters.get("temperature")
        params["max_retries"] = RuntimeParameters.get("max_retries")
        params["request_timeout"] = RuntimeParameters.get("request_timeout")
        params["prompt_feature_name"] = RuntimeParameters.get("prompt_feature_name")
        params["target_feature_name"] = RuntimeParameters.get("target_feature_name")
        params["stuff_prompt"] = RuntimeParameters.get("stuff_prompt")
        params["dr_credential_name"] = RuntimeParameters.get("dr_credential_name")
        params["openai_api_key"] = RuntimeParameters.get(params["dr_credential_name"])[
            "apiToken"
        ]
    except ValueError as e:
        print(f"Error loading runtime parameters: {e}. Defaulting to local run mode.")
        from local_helpers import get_kedro_catalog

        project_root = "../../"
        catalog = get_kedro_catalog(project_root)

        llm_credentials = catalog.load(
            "params:credentials.azure_openai_llm_credentials"
        )

        params["azure_endpoint"] = llm_credentials["azure_endpoint"]
        params["openai_api_key"] = llm_credentials["api_key"]
        params["openai_api_version"] = llm_credentials["api_version"]
        params["openai_deployment_name"] = llm_credentials["deployment_name"]

        params["embedding_model_name"] = catalog.load(
            "params:deploy_custom_rag.vectorstore.sentence_transformer_model_name"
        )

        params["temperature"] = catalog.load("params:deploy_custom_rag.llm.temperature")
        params["max_retries"] = catalog.load("params:deploy_custom_rag.llm.max_retries")
        params["request_timeout"] = catalog.load(
            "params:deploy_custom_rag.llm.request_timeout_secs"
        )
        params["prompt_feature_name"] = catalog.load(
            "params:deploy_custom_rag.custom_model.prompt_feature_name"
        )
        params["target_feature_name"] = catalog.load(
            "params:deploy_custom_rag.custom_model.target_name"
        )
        params["stuff_prompt"] = catalog.load(
            "params:deploy_custom_rag.llm.stuff_prompt"
        )

    chain = get_chain(input_dir, **params)
    return chain, params["prompt_feature_name"], params["target_feature_name"]


def score(data, model, **kwargs):
    """ "Orchestrate a RAG completion with our vector database."""
    chain, prompt_feature_name, target_feature_name = model

    full_result_dict: dict[str, list] = {target_feature_name: []}

    for i, row in data.iterrows():
        question = row[prompt_feature_name]
        chat_history = []
        if "messages" in row:
            messages = row["messages"]
            messages = json.loads(messages)
            for ia, a in enumerate(messages):
                message_dict = a
                if message_dict["type"] == "human":
                    message = HumanMessage.validate(message_dict)
                else:
                    message = AIMessage.validate(message_dict)
                chat_history.append(message)

        try:
            with get_openai_callback():
                chain_output = chain.invoke(
                    {
                        "input": question,
                        "chat_history": chat_history,
                    }
                )
            full_result_dict[target_feature_name].append(chain_output["answer"])
            for i, doc in enumerate(chain_output["context"]):
                if f"CITATION_CONTENT_{i}" not in full_result_dict:
                    full_result_dict[f"CITATION_CONTENT_{i}"] = []
                if f"CITATION_SOURCE_{i}" not in full_result_dict:
                    full_result_dict[f"CITATION_SOURCE_{i}"] = []
                if f"CITATION_PAGE_{i}" not in full_result_dict:
                    full_result_dict[f"CITATION_PAGE_{i}"] = []
                full_result_dict[f"CITATION_CONTENT_{i}"].append(doc.page_content)
                full_result_dict[f"CITATION_SOURCE_{i}"].append(
                    doc.metadata.get("source", "")
                )
                full_result_dict[f"CITATION_PAGE_{i}"].append(
                    doc.metadata.get("page", "")
                )

        except Exception as e:
            full_result_dict[target_feature_name].append(
                f"{e.__class__.__name__}: {str(e)}"
            )

    return DataFrame(full_result_dict)


if __name__ == "__main__":
    client, prompt_feature_name, target_feature_name = load_model(".")
    data = DataFrame(
        {
            prompt_feature_name: [
                "What is the capital of France?",
                "What is the capital of Germany?",
                "What is the capital of Italy?",
            ],
        }
    )
    result = score(data, (client, prompt_feature_name, target_feature_name))
    print(result)
