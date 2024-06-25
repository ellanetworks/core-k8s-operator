#!/usr/bin/env python3
# Copyright 2024 Guillaume
# See LICENSE file for licensing details.

"""Kubernetes charm for Ella."""

import logging
from typing import cast

import ops
from ops.charm import CollectStatusEvent

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class EllaK8SOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)
        self.framework.observe(self.on.update_status, self._configure)
        framework.observe(self.on["httpbin"].pebble_ready, self._configure)
        framework.observe(self.on.config_changed, self._configure)

    def _on_collect_status(self, event: CollectStatusEvent):
        """Handle the collect status event."""
        log_level = cast(str, self.model.config["log-level"]).lower()
        if log_level not in VALID_LOG_LEVELS:
            event.add_status(ops.BlockedStatus("Invalid log level"))
            return
        container = self.unit.get_container("httpbin")
        if not container.can_connect():
            event.add_status(ops.WaitingStatus("waiting for Pebble API"))
            return
        event.add_status(ops.ActiveStatus())

    def _configure(self, event: ops.ConfigChangedEvent):
        """Handle changed configuration.

        Change this example to suit your needs. If you don't need to handle config, you can remove
        this method.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        log_level = cast(str, self.model.config["log-level"]).lower()

        if log_level not in VALID_LOG_LEVELS:
            logger.warning("Invalid log level '%s'", log_level)
            return
        container = self.unit.get_container("httpbin")
        if not container.can_connect():
            logger.warning("Pebble API is not ready")
            return
        container.add_layer("httpbin", self._pebble_layer, combine=True)
        container.replan()
        logger.debug("Log level for gunicorn changed to '%s'", log_level)

    @property
    def _pebble_layer(self) -> ops.pebble.LayerDict:
        """Return a dictionary representing a Pebble layer."""
        return {
            "summary": "httpbin layer",
            "description": "pebble config layer for httpbin",
            "services": {
                "httpbin": {
                    "override": "replace",
                    "summary": "httpbin",
                    "command": "gunicorn -b 0.0.0.0:80 httpbin:app -k gevent",
                    "startup": "enabled",
                    "environment": {
                        "GUNICORN_CMD_ARGS": f"--log-level {self.model.config['log-level']}"
                    },
                }
            },
        }


if __name__ == "__main__":  # pragma: nocover
    ops.main(EllaK8SOperatorCharm)  # type: ignore
