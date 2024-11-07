# Copyright 2024 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

import datarobot as dr
import pulumi
import pulumi_datarobot as datarobot
import yaml

from pulumi_utils.helpers import ensure_app_settings, get_deployment_url

try:
    usecase_id = Path("data/outputs/use_case_id.txt").read_text()
    champion_rag_model_id = Path(
        "data/outputs/registered_custom_model_version_id.txt"
    ).read_text()
    with open(Path("conf/base/globals.yml")) as f:
        globals = yaml.safe_load(f)
        project_name = globals["project_name"]
except FileNotFoundError as e:
    raise FileNotFoundError(
        "The champion RAG model was not found in the outputs. Please run the 'kedro' pipeline."
    ) from e


# Set prediction environment
prediction_environment = datarobot.PredictionEnvironment(
    resource_name="ARAGOG Prediction Environment",
    platform=dr.enums.PredictionEnvironmentPlatform.DATAROBOT_SERVERLESS,
)


# Deploy Model
deployment_name = f"{project_name} Deployment"
champion_rag_model_deployment = datarobot.Deployment(
    resource_name=deployment_name,
    label=deployment_name,
    registered_model_version_id=champion_rag_model_id,
    prediction_environment_id=prediction_environment.id,
    use_case_ids=usecase_id,
)

application_name = f"{project_name} Application"
qa_application = datarobot.QaApplication(  # type: ignore[assignment]
    resource_name=application_name,
    name=application_name,
    deployment_id=champion_rag_model_deployment.id,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
)


qa_application.id.apply(ensure_app_settings)

rag_deployment_env_name: str = "RAG_DEPLOYMENT_ID"
app_env_name: str = "DATAROBOT_APPLICATION_ID"

pulumi.export(rag_deployment_env_name, champion_rag_model_deployment.id)
pulumi.export(app_env_name, qa_application.id)

pulumi.export(
    deployment_name,
    champion_rag_model_deployment.id.apply(get_deployment_url),
)
pulumi.export(
    application_name,
    qa_application.application_url,
)
