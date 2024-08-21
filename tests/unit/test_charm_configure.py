# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from ops.pebble import Layer
from scenario import Container, Context, ExecOutput, Mount, Relation, State

from charm import EllaK8SCharm
from ella import GnodeB

METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text())
NAMESPACE = "whatever"
DATABASE_LIB_PATH = "charms.data_platform_libs.v0.data_interfaces"


class TestCharmConfigure:
    patches_get_pod_ip = patch("charm.get_pod_ip")
    patcher_ella = patch("charm.Ella")
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
        TestCharmConfigure.patches_get_pod_ip.start()
        self.mock_ella = TestCharmConfigure.patcher_ella.start().return_value
        TestCharmConfigure.patcher_k8s_ebpf.start()
        TestCharmConfigure.patcher_k8s_amf_service.start()
        TestCharmConfigure.patcher_k8s_multus.start()
        self.mock_db_is_created = TestCharmConfigure.patcher_database_is_created.start()
        self.mock_db_relation_data = TestCharmConfigure.patcher_database_relation_data.start()

    @pytest.fixture(autouse=True)
    def context(self):
        self.ctx = Context(charm_type=EllaK8SCharm, juju_version="3.1")

    def test_given_config_file_not_written_when_pebble_ready_then_config_file_is_written(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount("/etc/ella/ella.yaml", local_file.name)},
                exec_mock={
                    ("ip", "route", "show"): ExecOutput(
                        return_code=0,
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

    def test_given_pebble_layer_not_created_when_pebble_ready_then_pebble_layer_created(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount("/etc/ella/ella.yaml", local_file.name)},
                exec_mock={
                    ("ip", "route", "show"): ExecOutput(
                        return_code=0,
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

            state_out = self.ctx.run(
                container.pebble_ready_event(),
                state_in,
            )

            assert state_out.containers[0].layers["ella"] == Layer(
                {
                    "summary": "ella layer",
                    "description": "pebble config layer for ella",
                    "services": {
                        "ella": {
                            "summary": "ella",
                            "startup": "enabled",
                            "override": "replace",
                            "command": "ella --config /etc/ella/ella.yaml",
                        }
                    },
                }
            )

    def test_given_gnb_relation_and_gnb_info_not_in_inventory_when_pebble_ready_then_gnb_added_to_inventory(
        self,
    ):
        self.mock_ella.configure_mock(
            **{
                "get_gnbs_from_inventory.return_value": [],
            },
        )

        gnb_relation = Relation(
            endpoint="fiveg_gnb_identity",
            interface="fiveg_gnb_identity",
            remote_app_data={
                "gnb_name": "gnb1",
                "tac": "1234",
            },
        )

        container = Container(
            name="ella",
            can_connect=True,
            mounts={"config": Mount("/etc/ella/ella.yaml", "/tmp/ella.yaml")},
            exec_mock={
                ("ip", "route", "show"): ExecOutput(
                    return_code=0,
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
        state_in = State(
            containers=[container], leader=True, relations=[db_relation, gnb_relation]
        )
        self.mock_db_relation_data.return_value = {
            db_relation.relation_id: {"uris": "mongodb://localhost:27017/ella"}
        }

        self.ctx.run(container.pebble_ready_event(), state_in)

        self.mock_ella.add_gnb_to_inventory.assert_called_once_with(
            gnb=GnodeB(name="gnb1", tac=1234)
        )

    def test_given_no_gnb_relation_and_gnb_info_in_inventory_when_pebble_ready_then_gnb_removed_from_inventory(
        self,
    ):
        self.mock_ella.configure_mock(
            **{
                "get_gnbs_from_inventory.return_value": [GnodeB(name="gnb1", tac=1234)],
            },
        )

        container = Container(
            name="ella",
            can_connect=True,
            mounts={"config": Mount("/etc/ella/ella.yaml", "/tmp/ella.yaml")},
            exec_mock={
                ("ip", "route", "show"): ExecOutput(
                    return_code=0,
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

        self.ctx.run(container.pebble_ready_event(), state_in)

        self.mock_ella.delete_gnb_from_inventory.assert_called_once_with(
            gnb=GnodeB(name="gnb1", tac=1234)
        )
