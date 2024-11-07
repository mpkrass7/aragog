# Copyright 2024 DataRobot, Inc. and its affiliates.
# All rights reserved.
# DataRobot, Inc.
# This is proprietary source code of DataRobot, Inc. and its
# affiliates.
# Released under the terms of DataRobot Tool and Utility Agreement.

"""
This is a boilerplate pipeline 'prep_dr_rag_custom_model'
generated using Kedro 0.19.3
"""

from datarobotx.idp.credentials import get_replace_or_create_credential
from datarobotx.idp.datasets import get_or_create_dataset_from_df
from datarobotx.idp.playgrounds import get_or_create_playground
from datarobotx.idp.vector_databases import get_or_create_vector_database_from_dataset
from kedro.pipeline import Pipeline, node
from kedro.pipeline.modular_pipeline import pipeline

from .nodes import (
    get_or_create_codespace_use_case,
    upload_vector_database,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                name="create_use_case",
                func=get_or_create_codespace_use_case,
                inputs={
                    "token": "params:credentials.datarobot.api_token",
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "name": "params:use_case.name",
                    "description": "params:use_case.description",
                },
                outputs="use_case_id",
            ),
            node(
                name="make_datarobot_RAG_credential",
                func=get_replace_or_create_credential,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "name": "params:dr_credential.name",
                    "credential_type": "params:dr_credential.credential_type",
                    "api_token": "params:credentials.azure_openai_llm_credentials.api_key",
                },
                outputs="dr_credential_id",
            ),
            node(
                name="create_playground",
                func=get_or_create_playground,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "use_case": "use_case_id",
                    "name": "params:playground.name",
                },
                outputs="playground_id",
            ),
            node(
                name="upload_knowledge_base_dataset",
                func=upload_vector_database,
                inputs={
                    "token": "params:credentials.datarobot.api_token",
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "use_case_id": "use_case_id",
                    "file_path": "rag_raw_docs",
                    "name": "params:vector_database.dataset_name",
                },
                outputs="vector_database_dataset_id",
            ),
            node(
                name="add_vector_database",
                func=get_or_create_vector_database_from_dataset,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "dataset_id": "vector_database_dataset_id",
                    "use_case": "use_case_id",
                    "chunking_parameters": "params:vector_database.chunking_parameters",
                    "name": "params:vector_database.name",
                },
                outputs="vector_database_id",
            ),
            node(
                name="upload_qa_pairs",
                func=get_or_create_dataset_from_df,
                inputs={
                    "token": "params:credentials.datarobot.api_token",
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "name": "params:qa_pairs.name",
                    "data_frame": "qa_pairs_dataset",
                    "use_cases": "use_case_id",
                },
                outputs="qa_pairs_dataset_id",
            ),
        ],
        inputs={"rag_raw_docs", "qa_pairs_dataset"},
        namespace="setup_playground",
        parameters={
            "params:credentials.datarobot.endpoint": "params:credentials.datarobot.endpoint",
            "params:credentials.datarobot.api_token": "params:credentials.datarobot.api_token",
            "params:credentials.azure_openai_llm_credentials.api_key": "params:credentials.azure_openai_llm_credentials.api_key",
        },
        outputs={
            "vector_database_id",
            "dr_credential_id",
            "playground_id",
            "use_case_id",
            "qa_pairs_dataset_id",
        },
    )
