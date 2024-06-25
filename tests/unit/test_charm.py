# Copyright 2024 Guillaume
# See LICENSE file for licensing details.


from unittest.mock import patch

import pytest
from charm import EllaK8SOperatorCharm
from ops import BlockedStatus, WaitingStatus, testing

NAMESPACE = "whatever"

class TestCharm:

    @pytest.fixture()
    def setup(self):
        pass

    @staticmethod
    def teardown() -> None:
        patch.stopall()

    @pytest.fixture(autouse=True)
    def harnesser(self, setup, request):
        self.harness = testing.Harness(EllaK8SOperatorCharm)
        self.harness.set_model_name(name=NAMESPACE)
        self.harness.begin()
        yield self.harness
        self.harness.cleanup()
        request.addfinalizer(self.teardown)

    def test_given_invalid_config_when_evaluate_status_then_blocked(self):
        self.harness.update_config({"log-level": "foobar"})

        self.harness.evaluate_status()

        assert self.harness.model.unit.status == BlockedStatus("Invalid log level")

    def test_given_cant_connect_when_evaluate_status_then_waiting(self):
        self.harness.update_config({"log-level": "info"})

        self.harness.evaluate_status()

        assert self.harness.model.unit.status == WaitingStatus("waiting for Pebble API")

    def test_given_valid_config_when_configure_then_service_is_running(self):
        expected_plan = {
            "services": {
                "httpbin": {
                    "override": "replace",
                    "summary": "httpbin",
                    "command": "gunicorn -b 0.0.0.0:80 httpbin:app -k gevent",
                    "startup": "enabled",
                    "environment": {"GUNICORN_CMD_ARGS": "--log-level info"},
                }
            },
        }

        self.harness.container_pebble_ready("httpbin")

        updated_plan = self.harness.get_container_pebble_plan("httpbin").to_dict()
        service = self.harness.model.unit.get_container("httpbin").get_service("httpbin")
        assert expected_plan == updated_plan
        assert service.is_running()

    def test_given_invalid_config_when_configure_then_service_not_running(self):
        self.harness.set_can_connect("httpbin", True)

        self.harness.update_config({"log-level": "foobar"})

        updated_plan = self.harness.get_container_pebble_plan("httpbin").to_dict()
        assert updated_plan == {}
