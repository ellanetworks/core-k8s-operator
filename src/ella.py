#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

"""Ella is a class that interacts with Ella."""

import logging
from dataclasses import dataclass
from typing import List

import requests

logger = logging.getLogger(__name__)

GNB_CONFIG_URL = "config/v1/inventory/gnb"
JSON_HEADER = {"Content-Type": "application/json"}


@dataclass
class GnodeB:
    """GnodeB is a class that represents a GnodeB."""

    name: str
    tac: int


class Ella:
    """Ella is a class that interacts with Ella."""

    def __init__(self, url: str):
        """Initialize Ella Client with the URL.

        Args:
            url (str): The URL. Example: http://localhost:8080
        """
        self.url = url

    def get_gnbs_from_inventory(self) -> List[GnodeB]:
        """Get the GnodeBs from the inventory."""
        inventory_url = f"{self.url}/{GNB_CONFIG_URL}"
        gnb_dict_list = self._get_resources_from_inventory(inventory_url)
        return [GnodeB(gnb_dict["name"], gnb_dict["tac"]) for gnb_dict in gnb_dict_list]

    def add_gnb_to_inventory(self, gnb: GnodeB) -> None:
        """Add a GnodeB to the inventory.

        Args:
            gnb (GnodeB): The GnodeB to add to the inventory.
        """
        inventory_url = f"{self.url}/{GNB_CONFIG_URL}/{gnb.name}"
        data = {"tac": gnb.tac}
        self._add_resource_to_inventory(inventory_url, gnb.name, data)

    def delete_gnb_from_inventory(self, gnb: GnodeB) -> None:
        """Delete a GnodeB from the inventory.

        Args:
            gnb (GnodeB): The GnodeB to delete from the inventory.
        """
        inventory_url = f"{self.url}/{GNB_CONFIG_URL}/{gnb.name}"
        self._delete_resource_from_inventory(inventory_url, gnb.name)

    def _get_resources_from_inventory(self, inventory_url: str) -> list:
        response = requests.get(inventory_url)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error("Failed to get resource from inventory: %s", e)
            return []
        resources = response.json()
        logger.info("Got %s from inventory", resources)
        return resources

    def _add_resource_to_inventory(self, url: str, resource_name: str, data: dict) -> None:
        response = requests.post(url, headers=JSON_HEADER, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error("Failed to add %s to ella: %s", resource_name, e)
        logger.info("%s added to ella", resource_name)

    def _delete_resource_from_inventory(self, inventory_url: str, resource_name: str) -> None:
        response = requests.delete(inventory_url)
        try:
            
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error("Failed to remove %s from webui: %s", resource_name, e)
        logger.info("%s removed from webui", resource_name)
