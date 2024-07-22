# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile
from pathlib import Path

import pytest
import yaml
from charm import EllaK8SCharm
from ops import ActiveStatus, WaitingStatus
from scenario import Container, Context, Mount, State

METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text())

NAMESPACE = "whatever"


class TestCharm:
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

    def test_given_config_file_not_written_when_update_status_then_config_file_is_written(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount("/etc/ella/ella.yaml", local_file.name)},
            )
            state_in = State(containers=[container])

            self.ctx.run(
                container.pebble_ready_event(),
                state_in,
            )
            assert local_file.read().decode() == 'mongoDBBinariesPath: "/usr/bin"'
