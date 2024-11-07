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

from kedro.pipeline import Pipeline, node
from kedro.pipeline.modular_pipeline import pipeline

from datarobotx.idp.llm_blueprints import (
    get_or_register_llm_blueprint_custom_model_version,
)
from datarobotx.idp.registered_model_versions import (
    get_or_create_registered_custom_model_version,
)

from .nodes import (
    add_custom_llm_to_playground,
    build_blueprints,
    get_best_blueprint,
    get_or_create_eval_dataset,
    run_all_aggregations,
    toggle_correctness,
    validate_custom_llm,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                name="create_pre_baked_blueprints",
                func=build_blueprints,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "playground": "playground_id",
                    "blueprint_list": "params:llm_blueprints.blueprints",
                    "system_prompt": "params:llm_blueprints.system_prompt",
                    "vector_database_id": "vector_database_id",
                },
                outputs="llm_blueprints",
            ),
            node(
                name="validate_custom_deployment",
                func=validate_custom_llm,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "use_case_id": "use_case_id",
                    "deployment_id": "custom_rag_deployment_id",
                    "prompt_feature_name": "params:custom_model.prompt_feature_name",
                },
                outputs="validation_id",
            ),
            node(
                name="add_custom_llm",
                func=add_custom_llm_to_playground,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "playground_id": "playground_id",
                    "deployment_id": "custom_rag_deployment_id",
                    "validation_id": "validation_id",
                },
                outputs="custom_llm_id",
            ),
            node(
                name="combine_playground_bps_with_custom_bp",
                func=lambda llm_blueprints, custom_llm_id: llm_blueprints
                + [custom_llm_id],
                inputs=["llm_blueprints", "custom_llm_id"],
                outputs="combined_bps",
            ),
            node(
                name="create_eval_dataset",
                func=get_or_create_eval_dataset,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "use_case_id": "use_case_id",
                    "eval_dataset_id": "qa_pairs_dataset_id",
                    "playground_id": "playground_id",
                },
                outputs="eval_config_id",
            ),
            node(
                name="toggle_on_correctness",
                func=toggle_correctness,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "use_case_id": "use_case_id",
                    "playground_id": "playground_id",
                    "eval_config_id": "eval_config_id",
                },
                outputs="correctness_is_toggled",
            ),
            node(
                name="run_correctness",
                func=run_all_aggregations,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "llm_bp_ids": "combined_bps",
                    "eval_config_id": "eval_config_id",
                    "eval_dataset_id": "qa_pairs_dataset_id",
                    "correctness_is_toggled": "correctness_is_toggled",
                },
                outputs="aggregation_dict",
            ),
            node(
                name="get_best_blueprint",
                func=get_best_blueprint,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "score_dict": "aggregation_dict",
                },
                outputs="best_bp_id",
            ),
            node(
                name="make_custom_model_version_args",
                func=lambda credential_id, azure_endpoint, base_environment_id: {
                    "runtime_parameter_values": [
                        {
                            "field_name": "OPENAI_API_KEY",
                            "type": "credential",
                            "value": credential_id,
                        },
                        {
                            "field_name": "OPENAI_API_BASE",
                            "type": "string",
                            "value": azure_endpoint,
                        },
                    ],
                    "base_environment_id": base_environment_id,
                },
                inputs={
                    "credential_id": "dr_credential_id",
                    "azure_endpoint": "params:credentials.azure_openai_llm_credentials.azure_endpoint",
                    "base_environment_id": "params:custom_model.base_environment_id",
                },
                outputs="custom_model_version_args",
            ),
            node(
                name="make_champion_blueprint_model_package",
                func=get_or_register_llm_blueprint_custom_model_version,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "llm_blueprint_id": "best_bp_id",
                    "custom_model_version_kwargs": "custom_model_version_args",
                    "prompt_column_name": "params:custom_model.prompt_feature_name",
                    "target_column_name": "params:custom_model.target_name",
                },
                outputs=[
                    "custom_champion_model_id",
                    "custom_champion_model_version_id",
                ],
            ),
            node(
                name="get_or_create_registered_model",
                func=get_or_create_registered_custom_model_version,
                inputs={
                    "endpoint": "params:credentials.datarobot.endpoint",
                    "token": "params:credentials.datarobot.api_token",
                    "custom_model_version_id": "custom_champion_model_version_id",
                    "registered_model_name": "params:registered_model_name",
                    "max_wait": "params:max_wait",
                },
                outputs="registered_champion_model_id",
            ),
        ],
        inputs={
            "vector_database_id",
            "playground_id",
            "use_case_id",
            "qa_pairs_dataset_id",
            "custom_rag_deployment_id",
            "dr_credential_id",
        },
        namespace="evaluate_blueprints",
        parameters={
            "params:credentials.datarobot.endpoint": "params:credentials.datarobot.endpoint",
            "params:credentials.datarobot.api_token": "params:credentials.datarobot.api_token",
            "params:credentials.azure_openai_llm_credentials.azure_endpoint": "params:credentials.azure_openai_llm_credentials.azure_endpoint",
        },
    )
