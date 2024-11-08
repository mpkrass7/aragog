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

import os
from pathlib import Path

import dotenv
import pulumi
import pulumi_datarobot as datarobot

from src.aragog.pulumi_utils.helpers import (
    ensure_app_settings,
    get_deployment_url,
    get_playground_url,
    get_stack,
)

project_name = get_stack()
dotenv.load_dotenv()

outputs_path = Path(f"data/{project_name}/outputs")
usecase_id_path = outputs_path / "use_case_id.txt"
champion_rag_model_id_path = outputs_path / "registered_champion_model_id.txt"
playground_id_path = outputs_path / "playground_id.txt"
rag_credential_path = outputs_path / "rag_dr_credential_id.txt"

try:
    usecase_id = usecase_id_path.read_text()
    playground_id = playground_id_path.read_text()
    credential_id = rag_credential_path.read_text()
    champion_rag_model_id = champion_rag_model_id_path.read_text()

except FileNotFoundError as e:
    raise FileNotFoundError(
        "Could not find required files. Have you run the Kedro project yet?"
    ) from e

# Deploy Model
deployment_name = f"{project_name} Deployment"
champion_rag_model_deployment = datarobot.Deployment(
    resource_name=deployment_name,
    label=deployment_name,
    registered_model_version_id=champion_rag_model_id,
    prediction_environment_id=os.environ["DATAROBOT_PREDICTION_ENVIRONMENT_ID"],
    use_case_ids=[usecase_id],
)

application_name = f"{project_name} Application"
qa_application = datarobot.QaApplication(  # type: ignore[assignment]
    resource_name=application_name,
    name=application_name,
    deployment_id=champion_rag_model_deployment.id,
    opts=pulumi.ResourceOptions(delete_before_replace=True),
    # use_case_ids=[usecase_id],
)

qa_application.id.apply(ensure_app_settings)

pulumi.export("USE_CASE_ID", usecase_id)
pulumi.export("PLAYGROUND_ID", playground_id)
pulumi.export("RAG_DEPLOYMENT_ID", champion_rag_model_deployment.id)
pulumi.export("DATAROBOT_APPLICATION_ID", qa_application.id)

pulumi.export(
    f"{project_name} Playground", get_playground_url(usecase_id, playground_id)
)
pulumi.export(
    deployment_name,
    champion_rag_model_deployment.id.apply(get_deployment_url),
)
pulumi.export(
    application_name,
    qa_application.application_url,
)
