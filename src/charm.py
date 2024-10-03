#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

"""Kubernetes charm for Ella."""

import json
import logging
from ipaddress import IPv4Address
from subprocess import CalledProcessError, check_output
from typing import List, Optional, Tuple

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.kubernetes_charm_libraries.v0.multus import (
    KubernetesMultusCharmLib,
    NetworkAnnotation,
    NetworkAttachmentDefinition,
)
from charms.sdcore_amf_k8s.v0.fiveg_n2 import N2Provides
from charms.sdcore_gnbsim_k8s.v0.fiveg_gnb_identity import (
    GnbIdentityRequires,
)
from jinja2 import Environment, FileSystemLoader
from lightkube.models.meta_v1 import ObjectMeta
from ops import (
    ActiveStatus,
    BlockedStatus,
    CharmBase,
    EventBase,
    Framework,
    ModelError,
    WaitingStatus,
    main,
)
from ops.charm import CollectStatusEvent
from ops.pebble import ConnectionError, ExecError, Layer

from charm_config import CharmConfig, CharmConfigInvalidError
from ella import Ella, GnodeB
from kubernetes_ella import (
    AMFService,
    EBPFVolume,
)

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
NMS_PORT = 5000
NGAPP_PORT = 38412
N2_RELATION_NAME = "fiveg-n2"
GNB_IDENTITY_RELATION_NAME = "fiveg_gnb_identity"


def render_config_file(
    interfaces: List[str], n3_address: str, database_url: str, database_name: str
) -> str:
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
        database_name=database_name,
    )
    return content


def get_pod_ip() -> Optional[str]:
    """Return the pod IP using juju client."""
    try:
        ip_address = check_output(["unit-get", "private-address"])
        return str(IPv4Address(ip_address.decode().strip())) if ip_address else None
    except (CalledProcessError, ValueError):
        return None


class EllaK8SCharm(CharmBase):
    """Charm the service."""

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
        self.n2_provider = N2Provides(self, N2_RELATION_NAME)
        self._gnb_identity = GnbIdentityRequires(self, GNB_IDENTITY_RELATION_NAME)
        self._kubernetes_multus = KubernetesMultusCharmLib(
            namespace=self.model.name,
            statefulset_name=self.model.app.name,
            container_name=self._container_name,
            pod_name=self._pod_name,
            cap_net_admin=True,
            network_annotations=self._generate_network_annotations(),
            network_attachment_definitions=self._network_attachment_definitions_from_config(),
            privileged=True,
        )
        self._ebpf_volume = EBPFVolume(
            namespace=self.model.name,
            container_name=self._container_name,
            app_name=self.model.app.name,
            unit_name=self.model.unit.name,
        )
        self.amf_service = AMFService(
            namespace=self.model.name,
            name=f"{self.app.name}-external",
            app_name=self.app.name,
            ngapp_port=NGAPP_PORT,
        )
        self.ella = Ella(url=self._ella_endpoint)
        self.unit.set_ports(NMS_PORT)
        self.framework.observe(self._database.on.database_created, self._configure)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)
        self.framework.observe(self.on.update_status, self._configure)
        self.framework.observe(self.on["ella"].pebble_ready, self._configure)
        self.framework.observe(self.on.config_changed, self._configure)
        self.framework.observe(self.on.fiveg_n2_relation_joined, self._configure)
        self.framework.observe(self._gnb_identity.on.fiveg_gnb_identity_available, self._configure)
        self.framework.observe(self.on.remove, self._on_remove)

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
        if not self._kubernetes_multus.multus_is_available():
            event.add_status(BlockedStatus("Multus is not installed or enabled"))
            logger.info("Multus is not installed or enabled")
            return
        if not self._kubernetes_multus.is_ready():
            event.add_status(WaitingStatus("Waiting for Multus to be ready"))
            logger.info("Waiting for Multus to be ready")
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
            self._charm_config: CharmConfig = CharmConfig.from_charm(charm=self)
        except CharmConfigInvalidError:
            return
        if not self.unit.is_leader():
            logger.info("Not a leader, skipping configuration")
            return
        if not self.container.can_connect():
            logger.warning("Pebble API is not ready")
            return
        if self._missing_relations():
            logger.warning("Missing relations")
            return
        if not self._kubernetes_multus.multus_is_available():
            logger.warning("Multus is not available")
            return
        self._kubernetes_multus.configure()
        self._configure_ebpf_volume()
        self._configure_amf_service()
        self._configure_routes()
        if not self._database_is_available():
            logger.warning("Database is not available")
            return
        changed = self._configure_config_file()
        self._configure_pebble(restart=changed)
        self._set_n2_information()
        self._sync_gnbs()

    def _on_remove(self, _: EventBase):
        self._kubernetes_multus.remove()

    def _configure_ebpf_volume(self):
        if not self._ebpf_volume.is_created():
            self._ebpf_volume.create()

    def _configure_amf_service(self):
        if not self.amf_service.is_created():
            self.amf_service.create()

    def _configure_routes(self):
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

    def _configure_config_file(self):
        desired_config_file = self._generate_config_file()
        if self._is_config_update_required(desired_config_file):
            self._push_config_file(content=desired_config_file)
            return True
        return False

    @property
    def _ella_endpoint(self) -> str:
        return f"http://{get_pod_ip()}:{NMS_PORT}"

    def _get_gnb_config_from_relations(self) -> List[GnodeB]:
        gnb_name_tac_list = []
        for gnb_identity_relation in self.model.relations.get(GNB_IDENTITY_RELATION_NAME, []):
            if not gnb_identity_relation.app:
                logger.warning(
                    "Application missing from the %s relation data",
                    GNB_IDENTITY_RELATION_NAME,
                )
                continue
            gnb_name = gnb_identity_relation.data[gnb_identity_relation.app].get("gnb_name", "")
            gnb_tac = gnb_identity_relation.data[gnb_identity_relation.app].get("tac", "")
            if gnb_name and gnb_tac:
                gnb_name_tac_list.append(GnodeB(name=gnb_name, tac=int(gnb_tac)))
        return gnb_name_tac_list

    def _sync_gnbs(self) -> None:
        """Sync the GNBs between the inventory and the relations."""
        inventory_gnb_list = self.ella.get_gnbs_from_inventory()
        relation_gnb_list = self._get_gnb_config_from_relations()
        for relation_gnb in relation_gnb_list:
            if relation_gnb not in inventory_gnb_list:
                self.ella.add_gnb_to_inventory(gnb=relation_gnb)
        for inventory_gnb in inventory_gnb_list:
            if inventory_gnb not in relation_gnb_list:
                self.ella.delete_gnb_from_inventory(gnb=inventory_gnb)

    def _set_n2_information(self) -> None:
        if not self._relation_created(N2_RELATION_NAME):
            return
        if not self._service_is_running():
            return
        load_balancer_ip, load_balancer_hostname = self.amf_service.get_info()
        self.n2_provider.set_n2_information(
            amf_ip_address=load_balancer_ip,
            amf_hostname=load_balancer_hostname if load_balancer_hostname else self._hostname(),
            amf_port=NGAPP_PORT,
        )

    def _hostname(self) -> str:
        """Build and returns the AMF hostname in the cluster."""
        return f"{self.model.app.name}-external.{self.model.name}.svc.cluster.local"

    def _service_is_running(self) -> bool:
        if not self.container.can_connect():
            return False
        try:
            service = self.container.get_service(self._service_name)
        except ModelError:
            return False
        return service.is_running()

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
        stdout, stderr = self._exec_command_in_workload(command="ip route show")
        if stderr:
            logger.error("Failed to get route information: %s", stderr)
            return False
        for line in stdout.splitlines():
            if f"{dst} via {via}" in line:
                return True
        return False

    def _create_default_route(self) -> None:
        """Create ip route towards core network."""
        _, stderr = self._exec_command_in_workload(
            command=f"ip route replace default via {self._charm_config.n6_gateway_ip} metric 110"
        )
        if stderr:
            logger.error("Failed to create default route (ExecError)")
            return
        logger.info("Default core network route created")

    def _create_ran_route(self) -> None:
        """Create ip route towards gnb-subnet."""
        stdout, stderr = self._exec_command_in_workload(
            command=f"ip route replace {self._charm_config.gnb_subnet} via {self._charm_config.n3_gateway_ip}"
        )
        if stderr:
            logger.error("Failed to create route to gnb-subnet (ExecError)")
            return
        logger.info("Route to gnb-subnet created")

    def _exec_command_in_workload(
        self, command: str, timeout: Optional[int] = 30, environment: Optional[dict] = None
    ) -> Tuple[str, str | None]:
        try:
            process = self.container.exec(
                command=command.split(),
                timeout=timeout,
                environment=environment,
            )
        except ExecError:
            logger.error("Failed executing command in workload (ExecError): %s", command)
            return "", "ExecError"
        except FileNotFoundError:
            logger.error("Failed executing command in workload (FileNotFoundError): %s", command)
            return "", "FileNotFoundError"
        except ConnectionError:
            logger.error("Failed executing command in workload (ConnectionError): %s", command)
            return "", "ConnectionError"
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
            database_name=DATABASE_NAME,
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

    @property
    def _pod_name(self) -> str:
        """Name of the unit's pod.

        Returns:
            str: A string containing the name of the current unit's pod.
        """
        return "-".join(self.model.unit.name.rsplit("/", 1))


if __name__ == "__main__":  # pragma: nocover
    main(EllaK8SCharm)  # type: ignore
