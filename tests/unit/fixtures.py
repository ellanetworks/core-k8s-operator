# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import patch

import pytest
from ops import testing

from charm import EllaK8SCharm


class EllaUnitTestFixtures:
    patches_get_pod_ip = patch("charm.get_pod_ip")
    patcher_ella = patch("charm.Ella")
    patcher_k8s_ebpf = patch("charm.EBPFVolume")
    patcher_k8s_amf_service = patch("charm.AMFService")
    patcher_k8s_multus = patch("charm.KubernetesMultusCharmLib")
    patcher_n2_provides_set_n2_information = patch("charm.N2Provides.set_n2_information")

    @pytest.fixture(autouse=True)
    def setup(self, request):
        EllaUnitTestFixtures.patches_get_pod_ip.start()
        self.mock_ella = EllaUnitTestFixtures.patcher_ella.start().return_value
        EllaUnitTestFixtures.patcher_k8s_ebpf.start()
        self.mock_k8s_amf_service = (
            EllaUnitTestFixtures.patcher_k8s_amf_service.start().return_value
        )
        EllaUnitTestFixtures.patcher_k8s_multus.start()
        self.mock_n2_provides_set_n2_information = (
            EllaUnitTestFixtures.patcher_n2_provides_set_n2_information.start()
        )
        yield
        request.addfinalizer(self.teardown)

    @staticmethod
    def teardown() -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def context(self):
        self.ctx = testing.Context(charm_type=EllaK8SCharm)
