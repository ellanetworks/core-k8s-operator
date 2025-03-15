#!/usr/bin/env python3
# Copyright 2024 Ella Networks
# See LICENSE file for licensing details.

"""Module use to handle Ella API calls."""

import logging
from dataclasses import dataclass
from typing import Any, List

import requests

logger = logging.getLogger(__name__)

STATUS_ENDPOINT = "/api/v1/status"
OPERATOR_ENDPOINT = "/api/v1/operator"
ROUTES_ENDPOINT = "/api/v1/routes"
USERS_ENDPOINT = "/api/v1/users"

JSON_HEADER = {"Content-Type": "application/json"}


@dataclass
class StatusResponse:
    """Response from Ella Core when checking the status."""

    initialized: bool
    version: str


@dataclass
class OperatorID:
    """Operator ID information."""

    mcc: str
    mnc: str


@dataclass
class OperatorSlice:
    """Operator Slice information."""

    sst: int
    sd: int


@dataclass
class OperatorTracking:
    """Operator Tracking information."""

    supported_tacs: List[str]


@dataclass
class OperatorHomeNetwork:
    """Operator Home Network information."""

    public_key: str


@dataclass
class Operator:
    """Operator information."""

    id: OperatorID
    slice: OperatorSlice
    tracking: OperatorTracking
    home_network: OperatorHomeNetwork


class EllaCore:
    """Handle Ella Core API calls."""

    def __init__(self, url: str, ca_certificate_path: str) -> None:
        if url.endswith("/"):
            url = url[:-1]
        self.url = url
        self._ca_certificate_path = ca_certificate_path
        self.token = None

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: any = None,  # type: ignore[reportGeneralTypeIssues]
        expect_json_response: bool = True,
    ) -> Any | None:
        """Make an HTTP request and handle common error patterns."""
        headers = JSON_HEADER
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = f"{self.url}{endpoint}"
        logger.info("%s request to %s", method, url)
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            verify=self._ca_certificate_path,
        )
        response.raise_for_status()
        if expect_json_response:
            json_response = response.json()
            return json_response
        else:
            return response.text

    def set_token(self, token: str) -> None:
        """Set the authentication token."""
        self.token = token

    def login(self, email: str, password: str) -> str | None:
        """Login to Ella Core.

        Returns:
            str: The authentication token.
        """
        data = {"email": email, "password": password}
        response = self._make_request("POST", "/api/v1/auth/login", data=data)
        if not response:
            logger.error("Failed to login to Ella Core.")
            return None
        result = response.get("result")
        if not result:
            logger.error("Failed to login to Ella Core.")
            return None
        token = result.get("token")
        if not token:
            logger.error("Failed to login to Ella Core.")
            return None
        logger.info("Logged in to Ella Core.")
        return token

    def get_status(self) -> StatusResponse | None:
        """Return if Ella Core is initialized."""
        try:
            response = self._make_request("GET", STATUS_ENDPOINT)
            if not response:
                return None
            result = response.get("result")
            if not result:
                logger.error("Failed to login to Ella Core.")
                return None
            initialized = result.get("initialized", False)
            version = result.get("version", "")
            return StatusResponse(initialized=initialized, version=version)
        except requests.exceptions.HTTPError:
            logger.warning("Failed to get status from Ella Core.")
            return None

    def is_initialized(self) -> bool:
        """Return if Ella Core is initialized."""
        status = self.get_status()
        return status.initialized if status else False

    def is_api_available(self) -> bool:
        """Return if Ella Core is reachable."""
        status = self.get_status()
        return status is not None

    def create_user(self, email: str, password: str, role: str) -> None:
        """Create a user in Ella Core."""
        data = {"email": email, "password": password, "role": role}
        self._make_request("POST", USERS_ENDPOINT, data=data)
        logger.info("User %s created in Ella Core", email)

    def create_route(self, destination: str, gateway: str, interface: str, metric: int):
        """Create a route in Ella Core."""
        route_config = {
            "destination": destination,
            "gateway": gateway,
            "interface": interface,
            "metric": metric,
        }
        self._make_request("POST", ROUTES_ENDPOINT, data=route_config)
        logger.info(f"Created route {destination}.")

    def get_operator(self) -> Operator | None:
        """Get the operator information."""
        response = self._make_request("GET", OPERATOR_ENDPOINT)
        if response is None:
            raise ValueError("Operator not found.")
        result = response.get("result", None)
        if result is None:
            raise ValueError("Result not found in operator")
        operator_id = result.get("id", None)
        if operator_id is None:
            raise ValueError("Operator ID not found.")
        operator_slice = result.get("slice", None)
        if operator_slice is None:
            raise ValueError("Operator Slice not found.")
        operator_tracking = result.get("tracking", None)
        if operator_tracking is None:
            raise ValueError("Operator Tracking not found.")
        operator_home_network = result.get("homeNetwork", None)
        if operator_home_network is None:
            raise ValueError("Operator Home Network not found.")
        mcc = operator_id.get("mcc", "")
        mnc = operator_id.get("mnc", "")
        sst = operator_slice.get("sst", 0)
        sd = operator_slice.get("sd", 0)
        supported_tacs = operator_tracking.get("supportedTacs", [])
        public_key = operator_home_network.get("publicKey", "")
        return Operator(
            id=OperatorID(
                mcc=mcc,
                mnc=mnc,
            ),
            slice=OperatorSlice(
                sst=sst,
                sd=sd,
            ),
            tracking=OperatorTracking(
                supported_tacs=supported_tacs,
            ),
            home_network=OperatorHomeNetwork(
                public_key=public_key,
            ),
        )
