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
        "ue-ip-pool": "172.250.1.0/16",
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
    "slice-id": {"sst": "1", "sd": "010203"},
    "site-device-group": [],
    "site-info": {
        "site-name": "demo",
        "plmn": {"mcc": "208", "mnc": "93"},
        "gNodeBs": [{"name": "demo-gnb1", "tac": 1}],
        "upf": {"upf-name": "upf-external", "upf-port": "8805"},
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
        now = time.time()
        timeout = 5
        while time.time() - now <= timeout:
            if requests.get(url).json():
                logger.info(f"Created device group {device_group_name}.")
                return
            else:
                time.sleep(1)
        raise TimeoutError("Timed out creating device group.")

    def create_network_slice(self, network_slice_name: str, device_groups: list) -> None:
        """Create a network slice.

        Args:
            network_slice_name (str): Network slice name
            device_groups (list): List of device groups to be included in the network slice
        """
        NETWORK_SLICE_CONFIG["site-device-group"] = device_groups
        url = f"{self.url}/config/v1/network-slice/{network_slice_name}"
        response = requests.post(url, json=NETWORK_SLICE_CONFIG)
        response.raise_for_status()
        now = time.time()
        timeout = 5
        while time.time() - now <= timeout:
            if requests.get(url).json():
                logger.info(f"Created network slice {network_slice_name}.")
                return
            else:
                time.sleep(1)
        raise TimeoutError("Timed out creating network slice.")
