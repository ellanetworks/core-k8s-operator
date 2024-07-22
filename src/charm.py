#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

"""Kubernetes charm for Ella."""

import logging

from jinja2 import Environment, FileSystemLoader
from ops import ActiveStatus, CharmBase, EventBase, Framework, WaitingStatus, main
from ops.charm import CollectStatusEvent
from ops.pebble import Layer

logger = logging.getLogger(__name__)

CONFIG_TEMPLATE_DIR_PATH = "src/templates/"
CONFIG_FILE_PATH = "/etc/ella/ella.yaml"
CONFIG_TEMPLATE_NAME = "ella.yaml.j2"


def render_config_file() -> str:
    """Render the config file.

    Returns:
        str: Content of the rendered config file.
    """
    jinja2_environment = Environment(loader=FileSystemLoader(CONFIG_TEMPLATE_DIR_PATH))
    template = jinja2_environment.get_template(CONFIG_TEMPLATE_NAME)
    content = template.render()
    return content


class EllaK8SCharm(CharmBase):
    """Charm the service."""

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self.container = self.unit.get_container("ella")
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)
        self.framework.observe(self.on.update_status, self._configure)
        framework.observe(self.on["ella"].pebble_ready, self._configure)
        framework.observe(self.on.update_status, self._configure)
        framework.observe(self.on.config_changed, self._configure)

    def _on_collect_status(self, event: CollectStatusEvent):
        """Handle the collect status event."""
        if not self.container.can_connect():
            event.add_status(WaitingStatus("waiting for Pebble API"))
            return
        if not self._config_file_is_written():
            event.add_status(WaitingStatus("waiting for config file"))
            return
        event.add_status(ActiveStatus())

    def _configure(self, _: EventBase):
        if not self.container.can_connect():
            logger.warning("Pebble API is not ready")
            return
        desired_config_file = self._generate_config_file()
        if config_update_required := self._is_config_update_required(desired_config_file):
            self._push_config_file(content=desired_config_file)
        self._configure_pebble(restart=config_update_required)

    def _configure_pebble(self, restart=False) -> None:
        """Configure the Pebble layer.

        Args:
            restart (bool): Whether to restart the container.
        """
        plan = self.container.get_plan()
        if plan.services != self._pebble_layer.services:
            self.container.add_layer("ella", self._pebble_layer, combine=True)
            self.container.replan()
            logger.info("New layer added: %s", self._pebble_layer)
        if restart:
            self.container.restart("ella")
            logger.info("Restarted container ")
            return
        self.container.replan()

    def _generate_config_file(self) -> str:
        return render_config_file()

    def _is_config_update_required(self, content: str) -> bool:
        if not self._config_file_is_written() or not self._config_file_content_matches(
            content=content
        ):
            return True
        return False

    def _push_config_file(self, content: str) -> None:
        self.container.push(path=CONFIG_FILE_PATH, source=content)
        logger.info("Config file written to %s", CONFIG_FILE_PATH)

    def _config_file_is_written(self) -> bool:
        return bool(self.container.exists(CONFIG_FILE_PATH))

    def _config_file_content_matches(self, content: str) -> bool:
        if not self.container.exists(path=CONFIG_FILE_PATH):
            return False
        existing_content = self.container.pull(path=CONFIG_FILE_PATH)
        if existing_content.read() != content:
            return False
        return True

    @property
    def _pebble_layer(self) -> Layer:
        """Return a dictionary representing a Pebble layer."""
        return Layer(
            {
                "summary": "ella layer",
                "description": "pebble config layer for ella",
                "services": {
                    "ella": {
                        "override": "replace",
                        "summary": "ella",
                        "command": "ella --config /etc/ella/ella.yaml",
                        "startup": "enabled",
                    }
                },
            }
        )


if __name__ == "__main__":  # pragma: nocover
    main(EllaK8SCharm)  # type: ignore
