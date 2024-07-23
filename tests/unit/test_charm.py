# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from charm import EllaK8SCharm
from ops import ActiveStatus, WaitingStatus
from scenario import Container, Context, ExecOutput, Mount, State

METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text())
NAMESPACE = "whatever"
IP_ROUTE_SHOW = """
default via 172.16.6.1 dev wlp9s0 proto dhcp src 172.16.6.111 metric 600
blackhole 10.1.19.128/26 proto 80
192.168.250.0/24 dev core proto kernel scope link src 192.168.250.1 linkdown
192.168.252.0/24 dev access proto kernel scope link src 192.168.252.1 linkdown
"""


class TestCharm:
    # patcher_check_output = patch("charm.check_output")
    patcher_k8s_ebpf = patch("charm.EBPFVolume")
    patcher_k8s_multus = patch("charm.KubernetesMultusCharmLib")

    @pytest.fixture(autouse=True)
    def setUp(self):
        TestCharm.patcher_k8s_ebpf.start()
        TestCharm.patcher_k8s_multus.start()
        # self.mock_check_output = TestCharm.patcher_check_output.start()

    @pytest.fixture(autouse=True)
    def context(self):
        self.ctx = Context(charm_type=EllaK8SCharm, juju_version="3.1")

    def test_given_cant_connect_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        container = Container(
            name="ella",
            can_connect=False,
        )

        state_in = State(
            containers=[container],
        )

        state_out = self.ctx.run("collect_unit_status", state_in)

        assert state_out.unit_status == WaitingStatus("waiting for Pebble API")

    def test_given_config_file_does_not_exist_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        container = Container(
            name="ella",
            can_connect=True,
        )

        state_in = State(
            containers=[container],
        )

        state_out = self.ctx.run("collect_unit_status", state_in)

        assert state_out.unit_status == WaitingStatus("waiting for config file")

    def test_given_config_file_exists_when_collect_unit_status_then_activestatus(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount("/etc/ella/ella.yaml", local_file.name)},
            )

            state_in = State(
                containers=[container],
            )

            state_out = self.ctx.run("collect_unit_status", state_in)

            assert state_out.unit_status == ActiveStatus("")

    def test_given_config_file_not_written_when_pebble_ready_then_config_file_is_written(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount("/etc/ella/ella.yaml", local_file.name)},
                exec_mock={
                    ("ip", "route", "show"):  # this is the command we're mocking
                    ExecOutput(
                        return_code=0,  # this data structure contains all we need to mock the call.
                        stdout=IP_ROUTE_SHOW,
                    ),
                    (
                        "ip",
                        "route",
                        "replace",
                        "default",
                        "via",
                        "192.168.250.1",
                        "metric",
                        "110",
                    ): ExecOutput(
                        return_code=0,
                        stdout="",
                    ),
                    (
                        "ip",
                        "route",
                        "replace",
                        "192.168.251.0/24",
                        "via",
                        "192.168.252.1",
                    ): ExecOutput(
                        return_code=0,
                        stdout="",
                    ),
                },
            )
            state_in = State(
                containers=[container],
                leader=True,
            )

            self.ctx.run(
                container.pebble_ready_event(),
                state_in,
            )
            assert local_file.read().decode() == 'mongoDBBinariesPath: "/usr/bin"'
