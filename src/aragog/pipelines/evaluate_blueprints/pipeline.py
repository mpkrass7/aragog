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

from .nodes import (
    add_custom_llm_to_playground,
    build_blueprints,
    get_max_score,
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
                outputs=None,
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
                },
                outputs="aggregation_dict",
            ),
            node(
                name="get_best_blueprint",
                func=get_max_score,
                inputs={"score_dict": "aggregation_dict"},
                outputs="best_bp_id",
            ),
        ],
        inputs={
            "vector_database_id",
            "playground_id",
            "use_case_id",
            "qa_pairs_dataset_id",
            "custom_rag_deployment_id",
        },
        namespace="evaluate_blueprints",
        parameters={
            "params:credentials.datarobot.endpoint": "params:credentials.datarobot.endpoint",
            "params:credentials.datarobot.api_token": "params:credentials.datarobot.api_token",
        },
        outputs={"best_bp_id"},
    )
