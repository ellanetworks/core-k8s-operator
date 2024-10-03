# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile

from ops.pebble import Layer
from scenario import Container, Exec, Mount, Relation, State

from ella import GnodeB
from tests.unit.fixtures import EllaUnitTestFixtures


class TestCharmConfigure(EllaUnitTestFixtures):
    def test_given_config_file_not_written_when_configure_then_config_file_is_written(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount(location="/etc/ella/ella.yaml", source=local_file.name)},
                execs={
                    Exec(
                        command_prefix=["ip", "route", "show"],
                        return_code=0,
                        stdout="",
                    ),
                    Exec(
                        command_prefix=[
                            "ip",
                            "route",
                            "replace",
                            "default",
                            "via",
                            "192.168.250.1",
                            "metric",
                            "110",
                        ],
                        return_code=0,
                        stdout="",
                    ),
                    Exec(
                        command_prefix=[
                            "ip",
                            "route",
                            "replace",
                            "192.168.251.0/24",
                            "via",
                            "192.168.252.1",
                        ],
                        return_code=0,
                        stdout="",
                    ),
                },
            )
            db_relation = Relation(endpoint="database", interface="mongodb_client")
            state_in = State(containers=[container], leader=True, relations=[db_relation])
            self.mock_db_relation_data.return_value = {
                db_relation.id: {"uris": "mongodb://localhost:27017/ella"}
            }

            self.ctx.run(self.ctx.on.pebble_ready(container), state_in)

            with open("tests/unit/expected_config.yaml", "r") as f:
                assert local_file.read().decode() == f.read()

    def test_given_pebble_layer_not_created_when_configure_then_pebble_layer_created(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = Container(
                name="ella",
                can_connect=True,
                mounts={"config": Mount(location="/etc/ella/ella.yaml", source=local_file.name)},
                execs={
                    Exec(
                        command_prefix=["ip", "route", "show"],
                        return_code=0,
                        stdout="",
                    ),
                    Exec(
                        command_prefix=[
                            "ip",
                            "route",
                            "replace",
                            "default",
                            "via",
                            "192.168.250.1",
                            "metric",
                            "110",
                        ],
                        return_code=0,
                        stdout="",
                    ),
                    Exec(
                        command_prefix=[
                            "ip",
                            "route",
                            "replace",
                            "192.168.251.0/24",
                            "via",
                            "192.168.252.1",
                        ],
                        return_code=0,
                        stdout="",
                    ),
                },
            )
            db_relation = Relation(endpoint="database", interface="mongodb_client")
            state_in = State(containers=[container], leader=True, relations=[db_relation])
            self.mock_db_relation_data.return_value = {
                db_relation.id: {"uris": "mongodb://localhost:27017/ella"}
            }

            state_out = self.ctx.run(self.ctx.on.pebble_ready(container), state_in)

            container = state_out.get_container("ella")
            assert container.layers["ella"] == Layer(
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

    def test_given_gnb_relation_and_gnb_info_not_in_inventory_when_configure_then_gnb_added_to_inventory(
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
            mounts={"config": Mount(location="/etc/ella/ella.yaml", source="/tmp/ella.yaml")},
            execs={
                Exec(
                    command_prefix=["ip", "route", "show"],
                    return_code=0,
                    stdout="",
                ),
                Exec(
                    command_prefix=[
                        "ip",
                        "route",
                        "replace",
                        "default",
                        "via",
                        "192.168.250.1",
                        "metric",
                        "110",
                    ],
                    return_code=0,
                    stdout="",
                ),
                Exec(
                    command_prefix=[
                        "ip",
                        "route",
                        "replace",
                        "192.168.251.0/24",
                        "via",
                        "192.168.252.1",
                    ],
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
            db_relation.id: {"uris": "mongodb://localhost:27017/ella"}
        }

        self.ctx.run(self.ctx.on.pebble_ready(container), state_in)

        self.mock_ella.add_gnb_to_inventory.assert_called_once_with(
            gnb=GnodeB(name="gnb1", tac=1234)
        )

    def test_given_no_gnb_relation_and_gnb_info_in_inventory_when_configure_then_gnb_removed_from_inventory(
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
            mounts={"config": Mount(location="/etc/ella/ella.yaml", source="/tmp/ella.yaml")},
            execs={
                Exec(
                    command_prefix=["ip", "route", "show"],
                    return_code=0,
                    stdout="",
                ),
                Exec(
                    command_prefix=[
                        "ip",
                        "route",
                        "replace",
                        "default",
                        "via",
                        "192.168.250.1",
                        "metric",
                        "110",
                    ],
                    return_code=0,
                    stdout="",
                ),
                Exec(
                    command_prefix=[
                        "ip",
                        "route",
                        "replace",
                        "192.168.251.0/24",
                        "via",
                        "192.168.252.1",
                    ],
                    return_code=0,
                    stdout="",
                ),
            },
        )
        db_relation = Relation(endpoint="database", interface="mongodb_client")
        state_in = State(containers=[container], leader=True, relations=[db_relation])
        self.mock_db_relation_data.return_value = {
            db_relation.id: {"uris": "mongodb://localhost:27017/ella"}
        }

        self.ctx.run(self.ctx.on.pebble_ready(container), state_in)

        self.mock_ella.delete_gnb_from_inventory.assert_called_once_with(
            gnb=GnodeB(name="gnb1", tac=1234)
        )

    def test_given_when_configure_then_n2_information_is_set(self):
        n2_relation = Relation(
            endpoint="fiveg-n2",
            interface="fiveg_n2",
        )
        db_relation = Relation(endpoint="database", interface="mongodb_client")
        container = Container(
            name="ella",
            can_connect=True,
            mounts={"config": Mount(location="/etc/ella/ella.yaml", source="/tmp/ella.yaml")},
            execs={
                Exec(
                    command_prefix=["ip", "route", "show"],
                    return_code=0,
                    stdout="",
                ),
                Exec(
                    command_prefix=[
                        "ip",
                        "route",
                        "replace",
                        "default",
                        "via",
                        "192.168.250.1",
                        "metric",
                        "110",
                    ],
                    return_code=0,
                    stdout="",
                ),
                Exec(
                    command_prefix=[
                        "ip",
                        "route",
                        "replace",
                        "192.168.251.0/24",
                        "via",
                        "192.168.252.1",
                    ],
                    return_code=0,
                    stdout="",
                ),
            },
        )
        state_in = State(
            containers=[container],
            relations=[n2_relation, db_relation],
            leader=True,
        )
        self.mock_db_relation_data.return_value = {
            db_relation.id: {"uris": "mongodb://localhost:27017/ella"}
        }
        self.mock_k8s_amf_service.get_info.return_value = "1.2.3.4", "my.hostname.com"

        self.ctx.run(self.ctx.on.pebble_ready(container), state_in)

        self.mock_n2_provides_set_n2_information.assert_called_once_with(
            amf_ip_address="1.2.3.4",
            amf_hostname="my.hostname.com",
            amf_port=38412,
        )
