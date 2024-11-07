# Copyright 2024 DataRobot, Inc. and its affiliates.
# All rights reserved.
# DataRobot, Inc.
# This is proprietary source code of DataRobot, Inc. and its
# affiliates.
# Released under the terms of DataRobot Tool and Utility Agreement.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pathlib
    import tempfile


def make_chunks(
    path_to_source_documents: pathlib.Path, chunk_size: int, chunk_overlap: int
) -> dict[str, Any]:
    """Convert raw documents into document chunks that can be ingested into a vector db.

    This node will often need to be tailored to your source documents.

    Parameters
    ----------
    path_to_source_documents : pathlib.Path
        Path to a directory containing the source documents
    chunk_size : int
        Document splitting chunk size
    chunk_overlap : int
        Document splitting overlap size

    Returns
    -------
    str :
        Document chunks as a list of langchain.schema.document.Document objects serialized to
        json. Each document should have its metadata['source'] attribute populated to allow
        the front end to report citations back to the user.
    """
    import re

    import nltk
    from langchain.text_splitter import MarkdownTextSplitter
    from langchain_community.document_loaders import DirectoryLoader

    def _format_metadata():
        """
        this function helps formatting the metadata to create a URL
        edit to your needs
        """
        https_string = re.compile(r".+(https://.+)$")

        for doc in docs:
            doc.metadata["source"] = (
                doc.metadata["source"]
                .replace("|", "/")
                .replace(str(path_to_source_documents.resolve()), "")
            )

            doc.metadata["source"] = re.sub(
                r"datarobot_docs/en/(.+)\.txt",
                r"https://docs.datarobot.com/en/docs/\1.html",
                doc.metadata["source"],
            )
            try:
                doc.metadata["source"] = https_string.findall(doc.metadata["source"])[0]
            except Exception:
                pass

    SOURCE_DOCUMENTS_FILTER = "**/*.*"  # "**/*.pdf" or "**/*.txt"

    loader = DirectoryLoader(
        str(path_to_source_documents.resolve()), glob=SOURCE_DOCUMENTS_FILTER
    )
    splitter = MarkdownTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
    nltk.download("averaged_perceptron_tagger_eng", quiet=True)

    data = loader.load()
    docs = splitter.split_documents(data)

    _format_metadata()

    return {"docs": [doc.to_json() for doc in docs]}


def make_vector_db_assets(
    docs: dict[str, Any], embedding_model_name: str
) -> tempfile.TemporaryDirectory:
    """Build the vector db and prepare it to be persisted.

    Parameters
    ----------
    docs : str
        json-serialized list of langchain.schema.document.Document objects corresponding
        to the chunked raw documents (and associated source metadata)
    embedding_model_name : str
        Name of the sentence-transformers embedding model to use with the vectorstore
        that will be built

    Returns
    -------
    tempfile.TemporaryDirectory :
        Temp directory containing all vector db assets that should be included in the
        custom model deployment.
    """
    import os
    import tempfile

    from langchain.schema import Document
    from langchain_community.vectorstores.faiss import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings

    d = tempfile.TemporaryDirectory()
    path_to_d = d.name

    documents = [Document(**doc["kwargs"]) for doc in docs["docs"]]

    embedding_function = HuggingFaceEmbeddings(
        model_name=embedding_model_name,
        cache_folder=os.path.join(path_to_d, "sentencetransformers"),
    )
    texts = [doc.page_content for doc in documents]
    metadatas = [doc.metadata for doc in documents]

    db = FAISS.from_texts(texts, embedding_function, metadatas=metadatas)
    db.save_local(os.path.join(path_to_d, "faiss_db"))
    return d
