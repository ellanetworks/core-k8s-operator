#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

"""Ella is a class that interacts with Ella."""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, List

import requests

logger = logging.getLogger(__name__)

GNB_CONFIG_URL = "config/v1/inventory/gnb"

JSON_HEADER = {"Content-Type": "application/json"}


@dataclass
class GnodeB:
    """GnodeB is a class that represents a GnodeB."""

    name: str
    tac: int


@dataclass
class CreateGnbParams:
    """Parameters to create a gNB."""

    tac: str


class Ella:
    """Ella is a class that interacts with Ella."""

    def __init__(self, url: str):
        """Initialize Ella Client with the URL.

        Args:
            url (str): The URL. Example: http://localhost:8080
        """
        self.url = url

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: any = None,  # type: ignore[reportGeneralTypeIssues]
    ) -> Any | None:
        """Make an HTTP request and handle common error patterns."""
        headers = JSON_HEADER
        url = f"{self.url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
            )
        except requests.RequestException as e:
            logger.error("HTTP request failed: %s", e)
            return None
        except OSError as e:
            logger.error("couldn't complete HTTP request: %s", e)
            return None
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Request failed: code %s",
                response.status_code,
            )
            return None
        try:
            json_response = response.json()
        except json.JSONDecodeError:
            return None
        return json_response

    def list_gnbs(self) -> List[GnodeB]:
        """Get the GnodeBs from the inventory."""
        response = self._make_request("GET", f"/{GNB_CONFIG_URL}")
        if not response:
            return []
        gnb_list = []
        for item in response:
            try:
                gnb_list.append(GnodeB(name=item["name"], tac=int(item["tac"])))
            except (ValueError, KeyError):
                logger.error("invalid gNB data: %s", item)
        return gnb_list

    def create_gnb(self, name: str, tac: int) -> None:
        """Create a gNB in the NMS inventory."""
        create_gnb_params = CreateGnbParams(tac=str(tac))
        self._make_request("POST", f"/{GNB_CONFIG_URL}/{name}", data=asdict(create_gnb_params))
        logger.info("gNB %s created in NMS", name)

    def delete_gnb(self, name: str) -> None:
        """Delete a gNB list from the NMS inventory."""
        self._make_request("DELETE", f"/{GNB_CONFIG_URL}/{name}")
        logger.info("UPF %s deleted from NMS", name)
