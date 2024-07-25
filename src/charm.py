#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

"""Kubernetes charm for Ella."""

import json
import logging
from typing import List, Optional, Tuple

from charm_config import CharmConfig, CharmConfigInvalidError
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires  # type: ignore[import]
from charms.kubernetes_charm_libraries.v0.multus import (
    KubernetesMultusCharmLib,
    NetworkAnnotation,
    NetworkAttachmentDefinition,
)
from jinja2 import Environment, FileSystemLoader
from kubernetes_ella import EBPFVolume
from lightkube.models.meta_v1 import ObjectMeta
from ops import (
    ActiveStatus,
    BlockedStatus,
    CharmBase,
    EventBase,
    EventSource,
    Framework,
    WaitingStatus,
    main,
)
from ops.charm import CharmEvents, CollectStatusEvent
from ops.pebble import ExecError, Layer

logger = logging.getLogger(__name__)

CONFIG_TEMPLATE_DIR_PATH = "src/templates/"
CONFIG_FILE_PATH = "/etc/ella/ella.yaml"
CONFIG_TEMPLATE_NAME = "ella.yaml.j2"
N3_INTERFACE_BRIDGE_NAME = "access-br"
N6_INTERFACE_BRIDGE_NAME = "core-br"
N3_NETWORK_ATTACHMENT_DEFINITION_NAME = "n3-net"
N6_NETWORK_ATTACHMENT_DEFINITION_NAME = "n6-net"
N3_INTERFACE_NAME = "n3"
N6_INTERFACE_NAME = "n6"
DATABASE_RELATION_NAME = "database"
DATABASE_NAME = "ella"


def render_config_file(interfaces: List[str], n3_address: str, database_url: str) -> str:
    """Render the config file.

    Returns:
        str: Content of the rendered config file.
    """
    jinja2_environment = Environment(loader=FileSystemLoader(CONFIG_TEMPLATE_DIR_PATH))
    template = jinja2_environment.get_template(CONFIG_TEMPLATE_NAME)
    content = template.render(
        interfaces=interfaces,
        n3_address=n3_address,
        database_url=database_url,
    )
    return content


class NadConfigChangedEvent(EventBase):
    """Event triggered when an existing network attachment definition is changed."""


class EllaCharmEvents(CharmEvents):
    """Kubernetes Ella charm events."""

    nad_config_changed = EventSource(NadConfigChangedEvent)


class EllaK8SCharm(CharmBase):
    """Charm the service."""

    on = EllaCharmEvents()  # type: ignore[reportAssignmentType]

    def __init__(self, framework: Framework):
        super().__init__(framework)
        self._container_name = self._service_name = "ella"
        self.container = self.unit.get_container(self._container_name)
        try:
            self._charm_config: CharmConfig = CharmConfig.from_charm(charm=self)
        except CharmConfigInvalidError:
            logger.error("Invalid configuration")
            return
        self._database = DatabaseRequires(
            self, relation_name=DATABASE_RELATION_NAME, database_name=DATABASE_NAME
        )
        self._kubernetes_multus = KubernetesMultusCharmLib(
            charm=self,
            container_name=self._container_name,
            cap_net_admin=True,
            network_annotations_func=self._generate_network_annotations,
            network_attachment_definitions_func=self._network_attachment_definitions_from_config,
            refresh_event=self.on.nad_config_changed,
            privileged=True,
        )
        self._ebpf_volume = EBPFVolume(
            namespace=self.model.name,
            container_name=self._container_name,
            app_name=self.model.app.name,
            unit_name=self.model.unit.name,
        )
        self.framework.observe(self._database.on.database_created, self._configure)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)
        self.framework.observe(self.on.update_status, self._configure)
        self.framework.observe(self.on["ella"].pebble_ready, self._configure)
        self.framework.observe(self.on.config_changed, self._configure)

    def _on_collect_status(self, event: CollectStatusEvent):
        """Handle the collect status event."""
        if not self.container.can_connect():
            event.add_status(WaitingStatus("waiting for Pebble API"))
            return
        if missing_relations := self._missing_relations():
            event.add_status(
                BlockedStatus(f"Waiting for {', '.join(missing_relations)} relation(s)")
            )
            logger.info("Waiting for %s  relation(s)", ", ".join(missing_relations))
            return
        if not self._database_is_available():
            event.add_status(WaitingStatus("Waiting for the database to be available"))
            logger.info("Waiting for the database to be available")
            return
        if not self._config_file_is_written():
            event.add_status(WaitingStatus("waiting for config file"))
            return
        event.add_status(ActiveStatus())

    def _configure(self, _: EventBase):
        try:  # workaround for https://github.com/canonical/operator/issues/736
            self._charm_config: CharmConfig = CharmConfig.from_charm(charm=self)  # type: ignore[no-redef]  # noqa: E501
        except CharmConfigInvalidError:
            return
        if not self.unit.is_leader():
            logger.info("Not a leader, skipping configuration")
            return
        if not self.container.can_connect():
            logger.warning("Pebble API is not ready")
            return
        if not self._kubernetes_multus.multus_is_available():
            logger.warning("Multus is not available")
            return
        self.on.nad_config_changed.emit()
        if not self._ebpf_volume.is_created():
            self._ebpf_volume.create()
        if not self._route_exists(
            dst="default",
            via=str(self._charm_config.n6_gateway_ip),
        ):
            self._create_default_route()
        if not self._route_exists(
            dst=str(self._charm_config.gnb_subnet),
            via=str(self._charm_config.n3_gateway_ip),
        ):
            self._create_ran_route()
        desired_config_file = self._generate_config_file()
        if config_update_required := self._is_config_update_required(desired_config_file):
            self._push_config_file(content=desired_config_file)
        self._configure_pebble(restart=config_update_required)

    def _missing_relations(self) -> List[str]:
        missing_relations = []
        for relation in [DATABASE_RELATION_NAME]:
            if not self._relation_created(relation):
                missing_relations.append(relation)
        return missing_relations

    def _relation_created(self, relation_name: str) -> bool:
        return bool(self.model.relations.get(relation_name))

    def _database_is_available(self) -> bool:
        return self._database.is_resource_created()

    def _route_exists(self, dst: str, via: str | None) -> bool:
        """Return whether the specified route exist."""
        try:
            stdout, stderr = self._exec_command_in_workload(command="ip route show")
        except ExecError as e:
            logger.error("Failed retrieving routes: %s", e.stderr)
            return False
        except FileNotFoundError as e:
            logger.error("Failed retrieving routes: %s", e)
            return False
        for line in stdout.splitlines():
            if f"{dst} via {via}" in line:
                return True
        return False

    def _create_default_route(self) -> None:
        """Create ip route towards core network."""
        try:
            self._exec_command_in_workload(
                command=f"ip route replace default via {self._charm_config.n6_gateway_ip} metric 110"
            )
        except ExecError as e:
            logger.error("Failed to create core network route: %s", e.stderr)
            return
        except FileNotFoundError as e:
            logger.error("Failed to create core network route: %s", e)
            return
        logger.info("Default core network route created")

    def _create_ran_route(self) -> None:
        """Create ip route towards gnb-subnet."""
        try:
            self._exec_command_in_workload(
                command=f"ip route replace {self._charm_config.gnb_subnet} via {self._charm_config.n3_gateway_ip}"
            )
        except ExecError as e:
            logger.error("Failed to create route to gnb-subnet: %s", e.stderr)
            return
        except FileNotFoundError as e:
            logger.error("Failed to create route to gnb-subnet: %s", e)
            return
        logger.info("Route to gnb-subnet created")

    def _exec_command_in_workload(
        self, command: str, timeout: Optional[int] = 30, environment: Optional[dict] = None
    ) -> Tuple[str, str | None]:
        process = self.container.exec(
            command=command.split(),
            timeout=timeout,
            environment=environment,
        )
        return process.wait_output()

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

    def _generate_network_annotations(self) -> List[NetworkAnnotation]:
        n3_network_annotation = NetworkAnnotation(
            name=N3_NETWORK_ATTACHMENT_DEFINITION_NAME,
            interface=N3_INTERFACE_NAME,
        )
        n6_network_annotation = NetworkAnnotation(
            name=N6_NETWORK_ATTACHMENT_DEFINITION_NAME,
            interface=N6_INTERFACE_NAME,
        )
        return [n3_network_annotation, n6_network_annotation]

    def _network_attachment_definitions_from_config(self) -> List[NetworkAttachmentDefinition]:
        n3_nad_config = {
            "cniVersion": "0.3.1",
            "ipam": {
                "type": "static",
                "addresses": [
                    {"address": f"{self._charm_config.n3_ip}/24"},
                ],
            },
            "capabilities": {"mac": True},
            "type": "bridge",
            "bridge": N3_INTERFACE_BRIDGE_NAME,
        }
        n6_nad_config = {
            "cniVersion": "0.3.1",
            "ipam": {
                "type": "static",
                "addresses": [
                    {"address": f"{self._charm_config.n6_ip}/24"},
                ],
            },
            "capabilities": {"mac": True},
            "type": "bridge",
            "bridge": N6_INTERFACE_BRIDGE_NAME,
        }

        n3_nad = NetworkAttachmentDefinition(
            metadata=ObjectMeta(name=(N3_NETWORK_ATTACHMENT_DEFINITION_NAME)),
            spec={"config": json.dumps(n3_nad_config)},
        )
        n6_nad = NetworkAttachmentDefinition(
            metadata=ObjectMeta(name=(N6_NETWORK_ATTACHMENT_DEFINITION_NAME)),
            spec={"config": json.dumps(n6_nad_config)},
        )
        return [n3_nad, n6_nad]

    def _generate_config_file(self) -> str:
        return render_config_file(
            interfaces=self._charm_config.interfaces,
            n3_address=str(self._charm_config.n3_ip),
            database_url=self._get_database_info()["uris"].split(",")[0],
        )

    def _get_database_info(self) -> dict:
        if not self._database_is_available():
            raise RuntimeError(f"Database `{DATABASE_NAME}` is not available")
        return self._database.fetch_relation_data()[self._database.relations[0].id]

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
