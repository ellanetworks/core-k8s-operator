# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import tempfile
from unittest.mock import Mock, patch

from ops import testing
from ops.pebble import Layer

from tests.unit.fixtures import EllaUnitTestFixtures


class TestCharmConfigure(EllaUnitTestFixtures):
    def test_given_config_file_not_written_when_configure_then_config_file_is_written(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = testing.Container(
                name="core",
                can_connect=True,
                mounts={
                    "config": testing.Mount(location="/etc/core/core.yaml", source=local_file.name)
                },
            )
            peer_relation = testing.PeerRelation(endpoint="core-peers", interface="core-peer")
            state_in = testing.State(
                containers=[container], leader=True, relations=[peer_relation]
            )
            with patch(
                "charm.EllaCore",
                return_value=Mock(
                    **{  # type: ignore
                        "is_api_available.return_value": False,
                        "is_initialized.return_value": False,
                    },
                ),
            ):
                self.ctx.run(self.ctx.on.pebble_ready(container), state_in)

            with open("tests/unit/expected_config.yaml", "r") as f:
                assert local_file.read().decode() == f.read()

    def test_given_pebble_layer_not_created_when_configure_then_pebble_layer_created(
        self,
    ):
        with tempfile.NamedTemporaryFile() as local_file:
            container = testing.Container(
                name="core",
                can_connect=True,
                mounts={
                    "config": testing.Mount(location="/etc/core/core.yaml", source=local_file.name)
                },
            )
            peer_relation = testing.PeerRelation(endpoint="core-peers", interface="core-peer")
            state_in = testing.State(
                containers=[container], leader=True, relations=[peer_relation]
            )
            with patch(
                "charm.EllaCore",
                return_value=Mock(
                    **{  # type: ignore
                        "is_api_available.return_value": False,
                        "is_initialized.return_value": False,
                    },
                ),
            ):
                state_out = self.ctx.run(self.ctx.on.pebble_ready(container), state_in)

            container = state_out.get_container("core")
            assert container.layers["core"] == Layer(
                {
                    "summary": "Ella Core layer",
                    "description": "pebble config layer for Ella Core",
                    "services": {
                        "core": {
                            "override": "replace",
                            "summary": "Ella Core Service",
                            "command": "core --config /etc/core/core.yaml",
                            "startup": "enabled",
                        }
                    },
                }
            )
