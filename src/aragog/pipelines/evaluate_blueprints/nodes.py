# Copyright 2024 DataRobot, Inc. and its affiliates.
# All rights reserved.
# DataRobot, Inc.
# This is proprietary source code of DataRobot, Inc. and its
# affiliates.
# Released under the terms of DataRobot Tool and Utility Agreement.
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import datarobot as dr
from datarobotx.idp.llm_blueprints import (
    get_or_create_llm_blueprint,
)

{
    "endpoint": "params:credentials.datarobot.endpoint",
    "token": "params:credentials.datarobot.api_token",
    "playground": "playground_id",
    "name": "params:llm_blueprint.name",
    "llm": "params:llm_blueprint.llm.id",
    "llm_settings": "params:llm_blueprint.llm_settings",
    "vector_database": "vector_database_id",
    "vector_database_settings": "params:llm_blueprint.vector_database_settings",
}


def build_blueprints(
    endpoint: str,
    token: str,
    playground: str,
    blueprint_list: list[dict[str, Any]],
    system_prompt: str,
    vector_database_id: str,
) -> list[str]:
    """Builds blueprints from a list of blueprints."""
    blueprints = []
    for blueprint in blueprint_list:
        blueprint["llm_settings"]["system_prompt"] = system_prompt
        blueprint_id = get_or_create_llm_blueprint(
            endpoint=endpoint,
            token=token,
            playground=playground,
            name=blueprint["name"],
            llm=blueprint["llm"]["id"],
            llm_settings=blueprint["llm_settings"],
            vector_database=vector_database_id,
            vector_database_settings=blueprint["vector_database_settings"],
        )
        blueprints.append(blueprint_id)
    return blueprints


def _find_existing_eval_dataset(
    endpoint, token, use_case_id, eval_dataset_id, playground_id
) -> str:
    client = dr.Client(endpoint=endpoint, token=token)

    API_URL = f"genai/evaluationDatasetConfigurations/?useCaseId={use_case_id}&playgroundId={playground_id}&sort=creationDate&limit=20&completedOnly=false"
    response = client.get(API_URL).json()
    try:
        eval_ds = next(
            eval_ds
            for eval_ds in response["data"]
            if eval_ds["datasetId"] == eval_dataset_id
        )
        return eval_ds["id"]
    except StopIteration:
        raise KeyError("No matching dataset found")


def get_or_create_eval_dataset(
    endpoint: str,
    token: str,
    use_case_id: str,
    eval_dataset_id: str,
    playground_id: str,
) -> str:
    client = dr.Client(endpoint=endpoint, token=token)

    try:
        return _find_existing_eval_dataset(
            endpoint, token, use_case_id, eval_dataset_id, playground_id
        )

    except KeyError:
        API_URL = f"{endpoint}/genai/evaluationDatasetConfigurations/"
        response = client.post(
            url=API_URL,
            data={
                "useCaseId": use_case_id,
                "isSyntheticDataset": "false",
                "datasetId": eval_dataset_id,
                "playgroundId": playground_id,
                "promptColumnName": "requierment",
                "responseColumnName": "response",
                "correctnessEnabled": "true",
            },
        ).json()
        eval_config_id = response["id"]
        return eval_config_id


def _get_existing_insights_config(endpoint: str, token: str, playground_id: str) -> str:
    client = dr.Client(endpoint=endpoint, token=token)

    try:
        # get existing configurations
        API_URL = f"genai/insights/{playground_id}/?withAggregationTypesOnly=false"
        response = client.get(API_URL).json()
    except dr.errors.ClientError as e:  # Staging route
        API_URL = f"genai/playgrounds/{playground_id}/supportedInsights/?withAggregationTypesOnly=false&productionOnly=false"

        response = client.get(API_URL).json()

    # drop None types from config
    insights_config = []
    for config in response["insightsConfiguration"]:
        insights_config.append({k: v for k, v in config.items() if v})

    return insights_config


def toggle_correctness(
    endpoint: str,
    token: str,
    use_case_id: str,
    playground_id: str,
    eval_config_id: str,
    blueprints: list[str],
) -> str:
    assert len(blueprints) > 0
    client = dr.Client(endpoint=endpoint, token=token)

    # get existing config
    config = _get_existing_insights_config(endpoint, token, playground_id)

    # add on correctness if not already existing
    if "correctness" not in [c["insightName"] for c in config]:
        # add correctness to config
        config.append(
            {
                "insightName": "correctness",
                "insightType": "Quality metric",
                "evaluationDatasetConfigurationId": eval_config_id,
                "executionStatus": "COMPLETED",
                "aggregationTypes": ["average"],
            }
        )

        # now add
        API_URL = "genai/insights/"
        client.post(
            url=API_URL,
            data={
                "useCaseId": use_case_id,
                "playgroundId": playground_id,
                "insightsConfiguration": config,
            },
        ).json()

    return True


def _find_existing_correctness_aggregation(
    endpoint, token, llm_bp_id, eval_config_id
) -> dict:
    client = dr.Client(endpoint=endpoint, token=token)

    API_URL = f"genai/evaluationDatasetMetricAggregations/?llmBlueprintIds={llm_bp_id}&nonErroredOnly=true"
    response = client.get(API_URL).json()

    try:
        configs = response["data"]
        aggregation = next(
            agg
            for agg in configs
            if agg["evaluationDatasetConfigurationId"] == eval_config_id
        )
        return aggregation
    except StopIteration:
        raise KeyError("No matching aggregation found")


def _wait_for_chat_completion(
    endpoint, token, chat_id, eval_dataset_id, timeout_secs
) -> None:
    dr.Client(endpoint=endpoint, token=token)

    # wait for all chats to finish
    waited_secs = 0
    while True:
        num_chats = len(dr.genai.ChatPrompt.list(chat=chat_id))
        if num_chats == dr.Dataset.get(eval_dataset_id).row_count:
            break
        elif waited_secs > timeout_secs:
            raise TimeoutError("Timed out waiting for dataset to process.")

        time.sleep(30)
        waited_secs += 30


def run_correctness_aggregation(
    endpoint, token, llm_bp_id, eval_config_id, eval_dataset_id
) -> dict:
    try:
        aggregation = _find_existing_correctness_aggregation(
            endpoint, token, llm_bp_id, eval_config_id
        )

    except KeyError:
        # kick off evaluation
        client = dr.Client(endpoint=endpoint, token=token)

        API_URL = "genai/evaluationDatasetMetricAggregations/"
        chat_name = f"Aggregated metrics {datetime.now():%Y-%m-%d %H:%M:%S}"
        response = client.post(
            url=API_URL,
            data={
                "chatName": chat_name,
                "llmBlueprintIds": [llm_bp_id],
                "evaluationDatasetConfigurationId": eval_config_id,
                "insightsConfiguration": [
                    {
                        "insightName": "correctness",
                        "insightType": "Quality metric",
                        "evaluationDatasetConfigurationId": eval_config_id,
                        "executionStatus": "COMPLETED",
                        "aggregationTypes": ["average"],
                    }
                ],
            },
        ).json()
        chat_id = response["chatIds"][0]

        # wait for chats to complete
        _wait_for_chat_completion(endpoint, token, chat_id, eval_dataset_id, 600)

        # get aggregated correctness score
        aggregation = _find_existing_correctness_aggregation(
            endpoint, token, llm_bp_id, eval_config_id
        )

    return aggregation


def get_correctness_score(
    endpoint: str, token: str, llm_bp_id, eval_config_id
) -> float:
    aggregation = _find_existing_correctness_aggregation(
        endpoint, token, llm_bp_id, eval_config_id
    )
    agg_value = aggregation["aggregationValue"]
    return agg_value


def run_all_aggregations(
    endpoint: str,
    token: str,
    llm_bp_ids: list[str],
    eval_config_id: str,
    eval_dataset_id: str,
    correctness_is_toggled: bool,
) -> dict:
    assert correctness_is_toggled
    agg_stats = {}
    for bp_id in llm_bp_ids:
        run_correctness_aggregation(
            endpoint, token, bp_id, eval_config_id, eval_dataset_id
        )
        score = get_correctness_score(endpoint, token, bp_id, eval_config_id)
        agg_stats[bp_id] = score

    return agg_stats


def _find_existing_llm_validation(endpoint, token, use_case_id, deployment_id):
    from datarobot.models.genai.custom_model_llm_validation import (
        CustomModelLLMValidation,
    )

    dr.Client(endpoint=endpoint, token=token)

    existing_validations = CustomModelLLMValidation.list(
        deployment=deployment_id, use_cases=use_case_id
    )
    if len(existing_validations) > 0:
        return existing_validations[0]
    else:
        raise KeyError("No matching validation found")


def validate_custom_llm(
    endpoint,
    token,
    use_case_id,
    deployment_id,
    prompt_feature_name,
) -> str:
    from datarobot.models.genai.custom_model_llm_validation import (
        CustomModelLLMValidation,
    )

    dr.Client(endpoint=endpoint, token=token)

    try:
        external_llm_validation = _find_existing_llm_validation(
            endpoint, token, use_case_id, deployment_id
        )

    except KeyError:
        # get information from deployment
        deployment = dr.Deployment.get(deployment_id)
        # prompt_feature_name = deployment.model['prompt']
        target_feature_name = deployment.model["target_name"]
        name = deployment.label

        # create validation
        external_llm_validation = CustomModelLLMValidation.create(
            prompt_column_name=prompt_feature_name,
            target_column_name=target_feature_name,
            deployment_id=deployment_id,
            name=name,
            use_case=use_case_id,
            wait_for_completion=True,
        )

    return external_llm_validation.id


def _find_existing_custom_bp(endpoint, token, playground_id, validation_id):
    from datarobot.models.genai.llm_blueprint import LLMBlueprint

    dr.Client(endpoint=endpoint, token=token)

    all_bps = LLMBlueprint.list(playground=playground_id)
    try:
        existing_bp = next(
            bp
            for bp in all_bps
            if bp.llm_settings.get("validation_id", "") == validation_id
        )
        return existing_bp

    except StopIteration:
        raise KeyError("No matching blueprint found")


def add_custom_llm_to_playground(
    endpoint,
    token,
    playground_id,
    deployment_id,
    validation_id,
) -> str:
    from datarobot.models.genai.llm_blueprint import LLMBlueprint

    dr.Client(endpoint=endpoint, token=token)

    try:
        custom_model_llm_blueprint = _find_existing_custom_bp(
            endpoint, token, playground_id, validation_id
        )

    except KeyError:
        # get name from deployment
        deployment = dr.Deployment.get(deployment_id)
        name = deployment.label

        # create blueprint
        custom_model_llm_blueprint = LLMBlueprint.create(
            playground=playground_id,
            name=name,
            llm="custom-model",
            llm_settings={
                "validation_id": validation_id,
                "external_llm_context_size": 4096,
            },
        )

    # make sure the blueprint has been saved
    if not custom_model_llm_blueprint.is_saved:
        custom_model_llm_blueprint.update(is_saved=True)

    return custom_model_llm_blueprint.id


def get_best_blueprint(endpoint: str, token: str, score_dict: dict[str, float]) -> str:
    client = dr.Client(endpoint=endpoint, token=token)
    best_bp_id = max(score_dict, key=score_dict.get)

    patch_route = f"genai/llmBlueprints/{best_bp_id}/"
    client.patch(patch_route, data={"isStarred": True})

    return best_bp_id
