# Copyright 2024 DataRobot, Inc. and its affiliates.
# All rights reserved.
# DataRobot, Inc.
# This is proprietary source code of DataRobot, Inc. and its
# affiliates.
# Released under the terms of DataRobot Tool and Utility Agreement.

from datarobotx.idp.common.asset_resolver import (
    merge_asset_paths,
    render_jinja_template,
)
from datarobotx.idp.custom_model_versions import get_or_create_custom_model_version
from datarobotx.idp.custom_models import get_or_create_custom_model
from datarobotx.idp.deployments import (
    get_replace_or_create_deployment_from_registered_model,
)
from datarobotx.idp.registered_model_versions import (
    get_or_create_registered_custom_model_version,
)
from kedro.pipeline import Pipeline, node
from kedro.pipeline.modular_pipeline import pipeline

from .nodes import (
    make_chunks,
    make_vector_db_assets,
)


def create_pipeline(**kwargs) -> Pipeline:
    nodes = [
        node(
            name="chunk_docs",
            func=make_chunks,
            inputs={
                "path_to_source_documents": "rag_raw_docs",
                "chunk_size": "params:vectorstore.chunk_size",
                "chunk_overlap": "params:vectorstore.chunk_overlap",
            },
            outputs="doc_chunks",
            tags=["checkpoint"],
        ),
        node(
            name="make_vector_DB",
            func=make_vector_db_assets,
            inputs={
                "docs": "doc_chunks",
                "embedding_model_name": "params:vectorstore.sentence_transformer_model_name",
            },
            outputs="vector_db_assets",
            tags=["checkpoint"],
        ),
        node(
            name="make_RAG_model_metadata",
            func=render_jinja_template,
            inputs={
                "template_file": "model_metadata_template",
                "custom_model_name": "params:custom_model.name",
                "target_type": "params:custom_model.target_type",
                "prompt_feature_name": "params:custom_model.prompt_feature_name",
                "target_feature_name": "params:custom_model.target_name",
                "credential_name": "params:dr_credential.name",
                "embedding_model_name": "params:vectorstore.sentence_transformer_model_name",
                "azure_endpoint": "params:credentials.azure_openai_llm_credentials.azure_endpoint",
                "openai_api_version": "params:credentials.azure_openai_llm_credentials.api_version",
                "openai_deployment_name": "params:credentials.azure_openai_llm_credentials.deployment_name",
                "temperature": "params:llm.temperature",
                "max_retries": "params:llm.max_retries",
                "request_timeout": "params:llm.request_timeout_secs",
                "stuff_prompt": "params:llm.stuff_prompt",
            },
            outputs="model_metadata",
        ),
        node(
            name="make_RAG_deployment_assets",
            func=merge_asset_paths,
            inputs=["vector_db_assets", "custom_py", "model_metadata", "requirements"],
            outputs="rag_deployment_assets",
            tags=["checkpoint"],
        ),
        node(
            name="make_RAG_custom_model",
            func=get_or_create_custom_model,
            inputs={
                "endpoint": "params:credentials.datarobot.endpoint",
                "token": "params:credentials.datarobot.api_token",
                "name": "params:custom_model.name",
                "target_type": "params:custom_model.target_type",
                "target_name": "params:custom_model.target_name",
            },
            outputs="rag_custom_model_id",
        ),
        node(
            name="make_runtime_parameters",
            func=lambda credential_name, credential_id: [
                {
                    "field_name": credential_name,
                    "type": "credential",
                    "value": credential_id,
                }
            ],
            inputs={
                "credential_name": "params:dr_credential.name",
                "credential_id": "dr_credential_id",
            },
            outputs="runtime_parameters",
        ),
        node(
            name="make_custom_rag_model_version",
            func=get_or_create_custom_model_version,
            inputs={
                "endpoint": "params:credentials.datarobot.endpoint",
                "token": "params:credentials.datarobot.api_token",
                "custom_model_id": "rag_custom_model_id",
                "base_environment_id": "params:custom_model.base_environment_id",
                "folder_path": "rag_deployment_assets",
                "runtime_parameter_values": "runtime_parameters",
                "max_wait": "params:max_wait",
            },
            outputs="rag_custom_model_version_id",
        ),
        node(
            name="make_custom_rag_registered_model",
            func=get_or_create_registered_custom_model_version,
            inputs={
                "endpoint": "params:credentials.datarobot.endpoint",
                "token": "params:credentials.datarobot.api_token",
                "custom_model_version_id": "rag_custom_model_version_id",
                "registered_model_name": "params:custom_model.registered_model_name",
                "max_wait": "params:max_wait",
            },
            outputs="registered_custom_model_version_id",
        ),
        node(
            name="create_deployment",
            func=get_replace_or_create_deployment_from_registered_model,
            inputs={
                "endpoint": "params:credentials.datarobot.endpoint",
                "token": "params:credentials.datarobot.api_token",
                "prediction_environment_id": "params:credentials.datarobot.prediction_environment_id",
                "registered_model_version_id": "registered_custom_model_version_id",
                "registered_model_name": "params:custom_model.registered_model_name",
                "label": "params:custom_model.deployment_name",
                "max_wait": "params:max_wait",
            },
            outputs="custom_rag_deployment_id",
        ),
    ]
    pipeline_inst = pipeline(nodes)
    return pipeline(
        pipeline_inst,
        inputs={"rag_raw_docs", "dr_credential_id"},
        namespace="deploy_custom_rag",
        parameters={
            "params:credentials.azure_openai_llm_credentials.azure_endpoint": "params:credentials.azure_openai_llm_credentials.azure_endpoint",
            "params:credentials.azure_openai_llm_credentials.api_version": "params:credentials.azure_openai_llm_credentials.api_version",
            "params:credentials.azure_openai_llm_credentials.deployment_name": "params:credentials.azure_openai_llm_credentials.deployment_name",
            "params:credentials.datarobot.endpoint": "params:credentials.datarobot.endpoint",
            "params:credentials.datarobot.api_token": "params:credentials.datarobot.api_token",
            "params:credentials.datarobot.prediction_environment_id": "params:credentials.datarobot.prediction_environment_id",
            "params:dr_credential.name": "params:setup_playground.dr_credential.name",
        },
        outputs={
            "custom_rag_deployment_id",
        },
    )
