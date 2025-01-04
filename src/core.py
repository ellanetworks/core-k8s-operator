#!/usr/bin/env python3
# Copyright 2024 Ella Networks
# See LICENSE file for licensing details.

"""Module use to handle Ella API calls."""

import json
import logging
from dataclasses import asdict, dataclass
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

STATUS_URL = "/api/v1/status"
LOGIN_URL = "/api/v1/auth/login"
LOOKUP_TOKEN_URL = "/api/v1/auth/lookup-token"
USERS_URL = "/api/v1/users"
RADIOS_URL = "/api/v1/radios"

JSON_HEADER = {"Content-Type": "application/json"}


@dataclass
class Response:
    """Response from Ella Core."""

    result: any  # type: ignore[reportGeneralTypeIssues]
    error: str


@dataclass
class StatusResponse:
    """Response from Ella Core when checking the status."""

    initialized: bool
    version: str


@dataclass
class LoginParams:
    """Parameters to login to Notary."""

    username: str
    password: str


@dataclass
class LoginResponse:
    """Response from Notary when logging in."""

    token: str


@dataclass
class CreateUserParams:
    """Parameters to create a user in Notary."""

    username: str
    password: str


@dataclass
class CreateUserResponse:
    """Response from Notary when creating a user."""

    message: str


@dataclass
class Radio:
    """Response from Ella Core when getting a radio."""

    name: str
    tac: str


@dataclass
class CreateRadioParams:
    """Parameters to create a radio in Ella Core."""

    name: str
    tac: str


@dataclass
class CreateRadioResponse:
    """Response from Ella Core when creating a radio."""

    message: str


class EllaCore:
    """Handle Ella Core API calls."""

    def __init__(self, url: str, ca_path: str | bool = False):
        self.url = url
        self.ca_path = ca_path

    def _make_request(
        self,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        data: any = None,  # type: ignore[reportGeneralTypeIssues]
    ) -> Response | None:
        """Make an HTTP request and handle common error patterns."""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        url = f"{self.url}{endpoint}"
        try:
            req = requests.request(
                method=method,
                url=url,
                verify=self.ca_path,
                headers=headers,
                json=data,
            )
        except requests.RequestException as e:
            logger.error("HTTP request failed: %s", e)
            return None
        except OSError as e:
            logger.error("couldn't complete HTTP request: %s", e)
            return None

        response = self._get_result(req)
        try:
            req.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Request failed: code %s, %s",
                req.status_code,
                response.error if response else "unknown",
            )
            return None
        return response

    def _get_result(self, req: requests.Response) -> Response | None:
        """Return the response from a request."""
        try:
            response = req.json()
        except json.JSONDecodeError:
            return None
        return Response(
            result=response.get("result"),
            error=response.get("error"),
        )

    def is_initialized(self) -> bool:
        """Return if the Notary server is initialized."""
        status = self.get_status()
        return status.initialized if status else False

    def is_api_available(self) -> bool:
        """Return if Ella Core is reachable."""
        status = self.get_status()
        return status is not None

    def get_version(self) -> str | None:
        """Return the version of the Notary server."""
        status = self.get_status()
        return status.version if status else None

    def get_status(self) -> StatusResponse | None:
        """Return the Ella Core status."""
        response = self._make_request("GET", STATUS_URL)
        if response and response.result:
            return StatusResponse(
                initialized=response.result.get("initialized"),
                version=response.result.get("version"),
            )
        return None

    def token_is_valid(self, token: str) -> bool:
        """Return if the token is still valid by attempting to connect to an endpoint."""
        response = self._make_request("POST", LOOKUP_TOKEN_URL, token=token)
        if response and response.result:
            return response.result.get("valid")
        return False

    def login(self, username: str, password: str) -> LoginResponse | None:
        """Login to notary by sending the username and password and return a Token."""
        login_params = LoginParams(username=username, password=password)
        response = self._make_request("POST", LOGIN_URL, data=asdict(login_params))
        if response and response.result:
            return LoginResponse(
                token=response.result.get("token"),
            )
        return None

    def create_first_user(self, username: str, password: str) -> CreateUserResponse | None:
        """Create the first admin user."""
        create_user_params = CreateUserParams(username=username, password=password)
        response = self._make_request("POST", USERS_URL, data=asdict(create_user_params))
        if response and response.result:
            return CreateUserResponse(
                message=response.result.get("message"),
            )
        return None

    def create_radio(self, name: str, tac: str, token: str) -> CreateRadioResponse | None:
        """Create a radio in Ella Core."""
        create_radio_params = CreateRadioParams(name=name, tac=tac)
        response = self._make_request(
            "POST", RADIOS_URL, token=token, data=asdict(create_radio_params)
        )
        if response and response.result:
            return CreateRadioResponse(
                message=response.result.get("message"),
            )
        return None

    def list_radios(self, token: str) -> List[Radio]:
        """Get the radios from the inventory."""
        response = self._make_request("GET", RADIOS_URL, token=token)
        if response and response.result:
            return [
                Radio(
                    name=radio.get("name"),
                    tac=radio.get("tac"),
                )
                for radio in response.result
            ]
        return []

    def delete_radio(self, name: str, token: str) -> None:
        """Delete a radio from the inventory."""
        self._make_request("DELETE", f"{RADIOS_URL}/{name}", token=token)
        logger.info("Radio %s deleted from Ella Core", name)
