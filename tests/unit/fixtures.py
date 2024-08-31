# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import patch

import pytest
from scenario import Context

from charm import EllaK8SCharm


class EllaUnitTestFixtures:
    patches_get_pod_ip = patch("charm.get_pod_ip")
    patcher_ella = patch("charm.Ella")
    patcher_k8s_ebpf = patch("charm.EBPFVolume")
    patcher_k8s_amf_service = patch("charm.AMFService")
    patcher_k8s_multus = patch("charm.KubernetesMultusCharmLib")
    patcher_database_is_created = patch("charm.DatabaseRequires.is_resource_created")
    patcher_database_relation_data = patch("charm.DatabaseRequires.fetch_relation_data")
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
        self.mock_db_is_created = EllaUnitTestFixtures.patcher_database_is_created.start()
        self.mock_db_relation_data = EllaUnitTestFixtures.patcher_database_relation_data.start()
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
        self.ctx = Context(charm_type=EllaK8SCharm)
