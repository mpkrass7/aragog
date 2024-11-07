import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import datarobot as dr
import pulumi
import yaml


def ensure_app_settings(app_id: str) -> None:
    try:
        dr.client.get_client().patch(
            f"customApplications/{app_id}/",
            json={"allowAutoStopping": True},
            timeout=60,
        )
    except Exception:
        pulumi.warn("Could not enable autostopping for the Application")


def get_deployment_url(deployment_id: str) -> str:
    """Translate deployment ID to GUI URL.

    Parameters
    ----------
    deployment_id : str
        DataRobot deployment id.
    endpoint: str
        DataRobot public API endpoint e.g. envir
    """
    parsed_dr_url = urlsplit(os.environ["DATAROBOT_ENDPOINT"])
    return f"{parsed_dr_url.scheme}://{parsed_dr_url.netloc}/console-nextgen/deployments/{deployment_id}/"


def get_playground_url(use_case_id: str, playground_id: str) -> None:
    """Translate use case id and playground id to GUI URL."""
    playground_path = "usecases/{}/playgrounds/{}/info".format(
        use_case_id, playground_id
    )
    parsed_dr_url = urlsplit(os.environ["DATAROBOT_ENDPOINT"])
    return f"{parsed_dr_url.scheme}://{parsed_dr_url.netloc}/{playground_path}"


use_case_path = (
    "usecases/672cd0b02751e7110ac6bfad/playgrounds/672cd0bb51b5cf9e51cd58d7/info"
)


def get_stack() -> str:
    """Retrieve the active pulumi stack

    Attempt to retrieve from the pulumi runtime
    If no stack selected, attempt to infer from an env var

    Allows subprocesses w/o access to the pulumi runtime to see the active stack even
    if `pulumi up -s` syntax is used with no selected stack.
    """
    try:
        stack = pulumi.get_stack()
        if stack != "stack":
            os.environ["PULUMI_STACK_CONTEXT"] = stack
            return stack
    except Exception:
        pass
    try:
        return os.environ["PULUMI_STACK_CONTEXT"]
    except KeyError:
        pass
    try:
        return subprocess.check_output(
            ["pulumi", "stack", "--show-name", "--non-interactive"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except subprocess.CalledProcessError:
        pass
    raise ValueError(
        (
            "Unable to retrieve the currently active stack. "
            "Verify you have selected created and selected a stack with `pulumi stack`."
        )
    )


def set_credentials_from_env(path_to_globals: Path, path_to_credentials: Path) -> None:
    globals_data = {"project_name": get_stack()}
    with open(path_to_globals, "w") as f:
        yaml.dump(globals_data, f)

    credentials_data = {
        "datarobot": {
            "endpoint": os.environ["DATAROBOT_ENDPOINT"],
            "api_token": os.environ["DATAROBOT_API_TOKEN"],
            "prediction_environment_id": os.environ[
                "DATAROBOT_PREDICTION_ENVIRONMENT_ID"
            ],
        },
        "azure_openai_llm_credentials": {
            "azure_endpoint": os.environ["OPENAI_API_BASE"],
            "api_key": os.environ["OPENAI_API_KEY"],
            "api_version": os.environ["OPENAI_API_VERSION"],
            "deployment_name": os.environ["OPENAI_API_DEPLOYMENT_ID"],
        },
    }

    with open(path_to_credentials, "w") as f:
        yaml.dump(credentials_data, f)
