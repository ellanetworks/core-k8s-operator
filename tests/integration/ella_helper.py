#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

SUBSCRIBER_CONFIG = {
    "UeId": "PLACEHOLDER",
    "plmnId": "20801",
    "opc": "981d464c7c52eb6e5036234984ad0bcf",
    "key": "5122250214c33e723a5dd523fc145fc0",
    "sequenceNumber": "16f3b3f70fc2",
}
DEVICE_GROUP_CONFIG = {
    "imsis": [],
    "site-info": "demo",
    "ip-domain-name": "pool1",
    "ip-domain-expanded": {
        "dnn": "internet",
        "ue-ip-pool": "172.250.0.0/16",
        "dns-primary": "8.8.8.8",
        "mtu": 1460,
        "ue-dnn-qos": {
            "dnn-mbr-uplink": 200000000,
            "dnn-mbr-downlink": 200000000,
            "bitrate-unit": "bps",
            "traffic-class": {"name": "platinum", "arp": 6, "pdb": 300, "pelr": 6, "qci": 8},
        },
    },
}
NETWORK_SLICE_CONFIG = {
    "slice-id": {"sst": "1", "sd": "102030"},
    "site-device-group": [],
    "site-info": {
        "site-name": "demo",
        "plmn": {"mcc": "001", "mnc": "01"},
        "upf": {"upf-name": "0.0.0.0", "upf-port": "8806"},
    },
}


class Ella:
    def __init__(self, url: str) -> None:
        """Initialize Ella Client with the URL.

        Args:
            url (str): The URL. Example: http://localhost:8080
        """
        self.url = url

    def create_subscriber(self, imsi: str) -> None:
        """Create a subscriber.

        Args:
            imsi (str): Subscriber's IMSI
        """
        SUBSCRIBER_CONFIG["UeId"] = imsi
        url = f"{self.url}/api/subscriber/imsi-{imsi}"
        response = requests.post(url=url, data=json.dumps(SUBSCRIBER_CONFIG))
        response.raise_for_status()
        logger.info(f"Created subscriber with IMSI {imsi}.")

    def create_device_group(self, device_group_name: str, imsis: list) -> None:
        """Create a device group.

        Args:
            device_group_name (str): Device group name
            imsis (list): List of IMSIs to be included in the device group
        """
        DEVICE_GROUP_CONFIG["imsis"] = imsis
        url = f"{self.url}/config/v1/device-group/{device_group_name}"
        response = requests.post(url, json=DEVICE_GROUP_CONFIG)
        response.raise_for_status()
        logger.info(f"Created device group {device_group_name}.")

    def wait_for_gnb(self, timeout: int = 300) -> tuple:
        """Wait for the gNB to be ready.

        Args:
            timeout (int): Timeout in seconds
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            response = requests.get(f"{self.url}/config/v1/inventory/gnb")
            response.raise_for_status()
            data = response.json()
            logger.info("Raw data: %s", data)
            if data:
                gnb_name = data[0]["name"]
                gnb_tac = data[0]["tac"]
                logger.info(f"Found gNB {gnb_name} with TAC {gnb_tac}.")
                return gnb_name, gnb_tac
            time.sleep(10)
        raise TimeoutError("Timeout while waiting for gNB.")

    def create_network_slice(
        self, network_slice_name: str, device_groups: list, gnb_name: str, gnb_tac: int
    ) -> None:
        """Create a network slice.

        Args:
            network_slice_name (str): Network slice name
            device_groups (list): List of device groups to be included in the network slice
            gnb_name (str): gNB name
            gnb_tac (int): gNB TAC
        """
        NETWORK_SLICE_CONFIG["site-device-group"] = device_groups
        NETWORK_SLICE_CONFIG["site-info"]["gNodeBs"] = [{"name": gnb_name, "tac": gnb_tac}]
        url = f"{self.url}/config/v1/network-slice/{network_slice_name}"
        response = requests.post(url, json=NETWORK_SLICE_CONFIG)
        response.raise_for_status()
        logger.info(f"Created network slice {network_slice_name}.")
