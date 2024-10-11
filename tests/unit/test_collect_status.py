# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile

from ops import ActiveStatus, BlockedStatus, WaitingStatus, testing

from tests.unit.fixtures import EllaUnitTestFixtures


class TestCharmCollectStatus(EllaUnitTestFixtures):
    def test_given_cant_connect_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        container = testing.Container(
            name="ella",
            can_connect=False,
        )

        state_in = testing.State(
            containers=[container],
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("waiting for Pebble API")

    def test_given_db_relation_not_created_when_collect_unit_status_then_blockedstatus(
        self,
    ):
        container = testing.Container(
            name="ella",
            can_connect=True,
        )

        state_in = testing.State(containers=[container], relations=[])

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == BlockedStatus("Waiting for database relation(s)")

    def test_given_db_not_available_when_collect_status_then_waitingstatus(self):
        self.mock_db_is_created.return_value = False
        container = testing.Container(
            name="ella",
            can_connect=True,
        )

        state_in = testing.State(
            containers=[container],
            relations=[testing.Relation(endpoint="database", interface="mongodb_client")],
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for the database to be available")

    def test_given_config_file_does_not_exist_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        self.mock_db_is_created.return_value = True
        container = testing.Container(
            name="ella",
            can_connect=True,
        )

        state_in = testing.State(
            containers=[container],
            relations=[testing.Relation(endpoint="database", interface="mongodb_client")],
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("waiting for config file")

    def test_given_config_file_exists_when_collect_unit_status_then_activestatus(
        self,
    ):
        self.mock_db_is_created.return_value = True
        with tempfile.NamedTemporaryFile() as local_file:
            container = testing.Container(
                name="ella",
                can_connect=True,
                mounts={
                    "config": testing.Mount(location="/etc/ella/ella.yaml", source=local_file.name)
                },
            )

            state_in = testing.State(
                containers=[container],
                relations=[testing.Relation(endpoint="database", interface="mongodb_client")],
            )

            state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

            assert state_out.unit_status == ActiveStatus("")
