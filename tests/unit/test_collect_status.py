# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile

from ops import ActiveStatus, WaitingStatus, testing

from tests.unit.fixtures import EllaUnitTestFixtures


class TestCharmCollectStatus(EllaUnitTestFixtures):
    def test_given_cant_connect_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        container = testing.Container(
            name="core",
            can_connect=False,
        )

        state_in = testing.State(
            containers=[container],
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("waiting for Pebble API")

    def test_given_peer_relation_not_created_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        container = testing.Container(
            name="core",
            can_connect=True,
        )

        state_in = testing.State(containers=[container], relations=[])

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for peer relation")

    def test_given_cert_not_available_when_collect_status_then_waitingstatus(self):
        container = testing.Container(
            name="core",
            can_connect=True,
        )

        state_in = testing.State(
            containers=[container],
            relations=[testing.PeerRelation(endpoint="core-peers", interface="core-peer")],
        )

        state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

        assert state_out.unit_status == WaitingStatus("Waiting for certificates to be generated")

    def test_given_config_file_does_not_exist_when_collect_unit_status_then_waitingstatus(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = testing.Container(
                name="core",
                can_connect=True,
                mounts={
                    "cert": testing.Mount(location="/etc/core/cert.pem", source=local_file.name),
                    "key": testing.Mount(location="/etc/core/key.pem", source=local_file.name),
                },
            )

            state_in = testing.State(
                containers=[container],
                relations=[testing.PeerRelation(endpoint="core-peers", interface="core-peer")],
            )

            state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

            assert state_out.unit_status == WaitingStatus("waiting for config file")

    def test_given_config_file_exists_when_collect_unit_status_then_activestatus(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = testing.Container(
                name="core",
                can_connect=True,
                mounts={
                    "cert": testing.Mount(location="/etc/core/cert.pem", source=local_file.name),
                    "key": testing.Mount(location="/etc/core/key.pem", source=local_file.name),
                    "config": testing.Mount(
                        location="/etc/core/core.yaml", source=local_file.name
                    ),
                },
            )

            state_in = testing.State(
                containers=[container],
                relations=[testing.PeerRelation(endpoint="core-peers", interface="core-peer")],
            )

            state_out = self.ctx.run(self.ctx.on.collect_unit_status(), state_in)

            assert state_out.unit_status == ActiveStatus()
