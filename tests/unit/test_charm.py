# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from charm import EllaK8SCharm
from ops import ActiveStatus, BlockedStatus, WaitingStatus
from scenario import Container, Context, ExecOutput, Mount, Relation, State

METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text())
NAMESPACE = "whatever"
DATABASE_LIB_PATH = "charms.data_platform_libs.v0.data_interfaces"


class TestCharm:
    patcher_k8s_ebpf = patch("charm.EBPFVolume")
    patcher_k8s_amf_service = patch("charm.AMFService")
    patcher_k8s_multus = patch("charm.KubernetesMultusCharmLib")
    patcher_database_is_created = patch(
        f"{DATABASE_LIB_PATH}.DatabaseRequires.is_resource_created"
    )
    patcher_database_relation_data = patch(
        f"{DATABASE_LIB_PATH}.DatabaseRequires.fetch_relation_data"
    )

    @pytest.fixture(autouse=True)
    def setUp(self):
        TestCharm.patcher_k8s_ebpf.start()
        TestCharm.patcher_k8s_amf_service.start()
        TestCharm.patcher_k8s_multus.start()
        self.mock_db_is_created = TestCharm.patcher_database_is_created.start()
        self.mock_db_relation_data = TestCharm.patcher_database_relation_data.start()

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

    def test_given_db_relation_not_created_when_collect_unit_status_then_blockedstatus(
        self,
    ):
        container = Container(
            name="ella",
            can_connect=True,
        )

        state_in = State(containers=[container], relations=[])

        state_out = self.ctx.run("collect_unit_status", state_in)

        assert state_out.unit_status == BlockedStatus("Waiting for database relation(s)")

    def test_given_db_not_available_when_collect_status_then_waitingstatus(self):
        self.mock_db_is_created.return_value = False
        container = Container(
            name="ella",
            can_connect=True,
        )

        state_in = State(
            containers=[container],
            relations=[Relation(endpoint="database", interface="mongodb_client")],
        )

        state_out = self.ctx.run("collect_unit_status", state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for the database to be available")

    def test_given_config_file_does_not_exist_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        self.mock_db_is_created.return_value = True
        container = Container(
            name="ella",
            can_connect=True,
        )

        state_in = State(
            containers=[container],
            relations=[Relation(endpoint="database", interface="mongodb_client")],
        )

        state_out = self.ctx.run("collect_unit_status", state_in)

        assert state_out.unit_status == WaitingStatus("waiting for config file")

    def test_given_config_file_exists_when_collect_unit_status_then_activestatus(
        self,
    ):
        self.mock_db_is_created.return_value = True
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount("/etc/ella/ella.yaml", local_file.name)},
            )

            state_in = State(
                containers=[container],
                relations=[Relation(endpoint="database", interface="mongodb_client")],
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
                        stdout="",
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
            db_relation = Relation(endpoint="database", interface="mongodb_client")
            state_in = State(containers=[container], leader=True, relations=[db_relation])
            self.mock_db_relation_data.return_value = {
                db_relation.relation_id: {"uris": "mongodb://localhost:27017/ella"}
            }

            self.ctx.run(
                container.pebble_ready_event(),
                state_in,
            )

            with open("tests/unit/expected_config.yaml", "r") as f:
                assert local_file.read().decode() == f.read()
