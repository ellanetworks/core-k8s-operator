#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import json
import logging
import time
from contextlib import contextmanager
from subprocess import CalledProcessError, call, check_output
from typing import Optional

logger = logging.getLogger(__name__)


def juju_wait_for_active_idle(model_name: str, timeout: int, time_idle: int = 10):
    """Wait for all application in a given model to be become Active-Idle.

    Args:
        model_name(str): Juju model name
        timeout(int): Time to wait for the applications to become Active-Idle
        time_idle(int): Time to wait after applications become Active-Idle

    Raises:
        TimeoutError: Raised if applications do not become Active-Idle within given time
    """
    now = time.time()
    with juju_context(model_name):
        while time.time() - now <= timeout:
            not_ready = {}
            for _, app_status in juju_status().items():
                for app_unit, unit_status in app_status["units"].items():
                    if "traefik" not in app_unit:
                        workload_status = unit_status["workload-status"]["current"]
                        unit_juju_status = unit_status["juju-status"]["current"]
                        if workload_status != "active" or unit_juju_status != "idle":
                            not_ready[app_unit] = (workload_status, unit_juju_status)
            if not_ready:
                for unit, status in not_ready.items():
                    logger.info(f"Waiting for {unit}. Current status is: {status}")
                logger.info("Sleeping for 10 seconds...")
                time.sleep(10)
                continue
            time.sleep(time_idle)
            logger.info("Deployment is ready!")
            logger.info(check_output(["juju", "status"]).decode())
            return
        raise TimeoutError("Timed out waiting for Juju model to be ready!")


def get_application_address(model_name: str, application_name: str) -> str:
    """Get Juju application IP address.

    Args:
        model_name(str): Juju model name
        application_name(str): Juju application name

    Returns:
        str: Juju application IP address

    Raises:
        JujuError: Custom error raised when getting application address fails
    """
    with juju_context(model_name):
        status = juju_status(application_name)
        try:
            return status[application_name].get("address")
        except KeyError as e:
            raise JujuError(f"Failed to get IP address of {application_name}!") from e


def get_unit_address(model_name: str, application_name: str, unit_number: int) -> str:
    """Get Juju application unit IP address.

    Args:
        model_name(str): Juju model name
        application_name(str): Juju application name
        unit_number(int): Application unit number

    Returns:
        str: Juju unit IP address

    Raises:
        JujuError: Custom error raised when getting unit address fails
    """
    with juju_context(model_name):
        unit_name = f"{application_name}/{unit_number}"
        status = juju_status(unit_name)
        try:
            return status[application_name]["units"][unit_name].get("address")
        except KeyError as e:
            raise JujuError(f"Failed to get IP address of {unit_name}!") from e


def juju_run_action(
    model_name: str, application_name: str, unit_number: int, action_name: str, timeout: int = 60
) -> dict:
    """Run Juju action.

    Args:
        model_name(str): Juju model name
        application_name(str): Juju application name
        unit_number(int): Application unit number
        action_name(str): Juju action name
        timeout(int): Time to wait for the action result

    Returns:
        dict: Action result

    Raises:
        JujuError: Custom error raised when running Juju action fails
    """
    with juju_context(model_name):
        unit_name = f"{application_name}/{unit_number}"
        try:
            cmd_out = check_output(
                ["juju", "run", unit_name, action_name, f"--wait={timeout}s", "--format=json"]
            ).decode()
            logger.info("Raw action output: %s", cmd_out)
            return json.loads(cmd_out)[unit_name]["results"]
        except (CalledProcessError, KeyError) as e:
            raise JujuError(f"Failed to run {action_name} action on {unit_name}!") from e


def juju_status(app_or_unit_name: Optional[str] = None) -> dict:
    """Return status of the model, application or unit.

    Args:
        app_or_unit_name(str): Juju application or unit name. If not specified, status
            model will be returned

    Returns:
        dict(str): Dictionary representing status of requested entity
    """
    juju_status_args = ["juju", "status", app_or_unit_name, "--format=json"]
    status = json.loads(check_output([arg for arg in juju_status_args if arg]).decode())
    return status["applications"]


def set_model_config(model_name: str, config: dict):
    """Set Juju model config.

    Args:
        model_name(str): Juju model name
        config(dict): Juju model config options in a form of a dictionary

    Raises:
        JujuError: Custom error raised when setting Juju model config fails
    """
    with juju_context(model_name):
        for model_key, value in config.items():
            try:
                call(["juju", "model-config", f"{model_key}={value}"])
            except CalledProcessError as e:
                raise JujuError(
                    f"Failed to set {model_key}={value} config for {model_name}"
                ) from e


def set_application_config(model_name: str, application_name: str, config: dict):
    """Set Juju model config.

    Args:
        model_name(str): Juju model name
        application_name(str): Juju application name
        config(dict): Juju model config options in a form of a dictionary

    Raises:
        JujuError: Custom error raised when setting Juju application config fails
    """
    with juju_context(model_name):
        for model_key, value in config.items():
            try:
                call(["juju", "config", application_name, f"{model_key}={value}"])
            except CalledProcessError as e:
                raise JujuError(
                    f"Failed to set {model_key}={value} config for {application_name}"
                ) from e
    juju_wait_for_active_idle(model_name, 60)


@contextmanager
def juju_context(model_name: str):
    """Allow changing currently active Juju model.

    Args:
        model_name(str): Juju model name

    Raises:
        JujuError: Custom error raised when changing Juju model fails
    """
    try:
        call(["juju", "switch", model_name])
        yield f"Current Juju model changed to {model_name}"
    except CalledProcessError as e:
        raise JujuError(f"Switching Juju model to {model_name} failed!") from e


class JujuError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
