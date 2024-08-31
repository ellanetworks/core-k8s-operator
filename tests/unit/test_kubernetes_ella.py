# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

from unittest.mock import Mock, patch

import pytest
from lightkube.models.core_v1 import (
    LoadBalancerIngress,
    LoadBalancerStatus,
    Service,
    ServiceStatus,
)

from kubernetes_ella import AMFService


class TestAMFService:
    patcher_lightkube_client = patch("lightkube.core.client.GenericSyncClient", new=Mock)
    patcher_lightkube_client_get = patch("lightkube.core.client.Client.get")

    @pytest.fixture(autouse=True)
    def setUp(self, request) -> None:
        TestAMFService.patcher_lightkube_client.start()
        self.mock_lightkube_client_get = TestAMFService.patcher_lightkube_client_get.start()
        request.addfinalizer(self.tearDown)

    @staticmethod
    def tearDown() -> None:
        patch.stopall()

    def test_given_empty_service_when_get_info_then_return_none(self):
        self.mock_lightkube_client_get.return_value = Service()
        amf_service = AMFService(
            namespace="whatever",
            app_name="ella-k8s",
            ngapp_port=1234,
            name="ella-k8s-external",
        )

        ip, hostname = amf_service.get_info()

        assert ip == ""
        assert hostname == ""

    def test_given_empty_service_with_only_ip_when_get_info_then_return_ip(self):
        self.mock_lightkube_client_get.return_value = Service(
            apiVersion="v1",
            kind="Service",
            status=ServiceStatus(
                conditions=None,
                loadBalancer=LoadBalancerStatus(
                    ingress=[
                        LoadBalancerIngress(hostname=None, ip="1.2.3.4", ipMode="VIP", ports=None)
                    ]
                ),
            ),
        )
        amf_service = AMFService(
            namespace="namespace",
            app_name="app_name",
            ngapp_port=1234,
            name="name",
        )

        ip, hostname = amf_service.get_info()

        assert ip == "1.2.3.4"
        assert hostname == ""

    def test_given_empty_service_with_only_hostname_when_get_info_then_return_hostname(self):
        self.mock_lightkube_client_get.return_value = Service(
            apiVersion="v1",
            kind="Service",
            status=ServiceStatus(
                conditions=None,
                loadBalancer=LoadBalancerStatus(
                    ingress=[
                        LoadBalancerIngress(hostname="hostname", ip=None, ipMode="VIP", ports=None)
                    ]
                ),
            ),
        )
        amf_service = AMFService(
            namespace="namespace",
            app_name="app_name",
            ngapp_port=1234,
            name="name",
        )

        ip, hostname = amf_service.get_info()

        assert ip == ""
        assert hostname == "hostname"

    def test_given_service_with_ip_and_hostname_when_get_info_then_return_ip_and_hostname(self):
        self.mock_lightkube_client_get.return_value = Service(
            apiVersion="v1",
            kind="Service",
            status=ServiceStatus(
                conditions=None,
                loadBalancer=LoadBalancerStatus(
                    ingress=[
                        LoadBalancerIngress(
                            hostname="hostname", ip="1.2.3.4", ipMode="VIP", ports=None
                        )
                    ]
                ),
            ),
        )
        amf_service = AMFService(
            namespace="namespace",
            app_name="app_name",
            ngapp_port=1234,
            name="name",
        )

        ip, hostname = amf_service.get_info()

        assert ip == "1.2.3.4"
        assert hostname == "hostname"
