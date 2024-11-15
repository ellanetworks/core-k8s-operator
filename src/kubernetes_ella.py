#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger

"""Kubernetes specific code for Ella."""

import logging
from typing import Iterable, Optional, Tuple

from lightkube.core.client import Client
from lightkube.core.exceptions import ApiError
from lightkube.models.apps_v1 import StatefulSetSpec
from lightkube.models.core_v1 import (
    Container,
    HostPathVolumeSource,
    ServicePort,
    ServiceSpec,
    Volume,
    VolumeMount,
    EmptyDirVolumeSource
)
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apps_v1 import StatefulSet
from lightkube.resources.core_v1 import Pod, Service

logger = logging.getLogger(__name__)


class EBPFVolume:
    """eBPF volume for Ella."""

    def __init__(self, namespace: str, container_name: str, app_name: str, unit_name: str):
        self.client = Client()  # type: ignore[reportArgumentType]
        self.namespace = namespace
        self.app_name = app_name
        self.unit_name = unit_name
        self.container_name = container_name
        self.ebpf_volumemount = VolumeMount(
            name="ebpf",
            mountPath="/sys/fs/bpf",
        )
        self.database_volumemount = VolumeMount(
            name="database",
            mountPath="/var/lib/ella",
        )
        self.ebpf_volume = Volume(
            name="ebpf",
            hostPath=HostPathVolumeSource(
                path="/sys/fs/bpf",
                type="",
            ),
        )
        self.database_volume = Volume(
            name="database",
            hostPath=EmptyDirVolumeSource(),
        )

    def is_created(self) -> bool:
        """Check if the eBPF volume is created."""
        return self._pod_is_patched() and self._statefulset_is_patched()

    def _pod_is_patched(self) -> bool:
        try:
            pod = self.client.get(Pod, name=self._pod_name, namespace=self.namespace)
        except ApiError as e:
            if e.status.reason == "Unauthorized":
                logger.debug("kube-apiserver not ready yet")
            else:
                logger.error("Could not get pod `%s`", self._pod_name)
                return False
            logger.info("Pod `%s` not found", self._pod_name)
            return False
        pod_has_volumemount = self._pod_contains_ebpf_volumemount(
            ebpf_volumemount=self.ebpf_volumemount,
            containers=pod.spec.containers,  # type: ignore[attr-defined]
            container_name=self.container_name,
        )
        logger.info("Pod `%s` has eBPF volume mounted: %s", self._pod_name, pod_has_volumemount)
        return pod_has_volumemount

    def _statefulset_is_patched(self) -> bool:
        try:
            statefulset = self.client.get(
                res=StatefulSet, name=self.app_name, namespace=self.namespace
            )
        except ApiError as e:
            if e.status.reason == "Unauthorized":
                logger.debug("kube-apiserver not ready yet")
            else:
                logger.error("Could not get statefulset `%s`", self.app_name)
                return False
            logger.info("Statefulset `%s` not found", self.app_name)
            return False

        contains_volume = self._statefulset_contains_ebpf_volume(
            statefulset_spec=statefulset.spec,  # type: ignore[attr-defined]
            ebpf_volume=self.ebpf_volume,
        )
        logger.info("Statefulset `%s` has eBPF volume: %s", self.app_name, contains_volume)
        return contains_volume

    @staticmethod
    def _statefulset_contains_ebpf_volume(
        statefulset_spec: StatefulSetSpec,
        ebpf_volume: Volume,
    ) -> bool:
        if not statefulset_spec.template.spec:
            logger.info("Statefulset has no template spec")
            return False
        if not statefulset_spec.template.spec.volumes:
            logger.info("Statefulset has no volumes")
            return False
        return ebpf_volume in statefulset_spec.template.spec.volumes

    @classmethod
    def _get_container(
        cls, container_name: str, containers: Iterable[Container]
    ) -> Optional[Container]:
        try:
            return next(iter(filter(lambda ctr: ctr.name == container_name, containers)))
        except StopIteration:
            logger.error("Container `%s` not found", container_name)
            return

    def _pod_contains_ebpf_volumemount(
        self,
        containers: Iterable[Container],
        container_name: str,
        ebpf_volumemount: VolumeMount,
    ) -> bool:
        container = self._get_container(container_name=container_name, containers=containers)
        if not container:
            return False
        if not container.volumeMounts:
            return False
        return ebpf_volumemount in container.volumeMounts

    def create(self) -> None:
        """Create the eBPF volume."""
        try:
            statefulset = self.client.get(
                res=StatefulSet, name=self.app_name, namespace=self.namespace
            )
        except ApiError:
            logger.error("Could not get statefulset `%s`", self.app_name)
            return

        containers: Iterable[Container] = statefulset.spec.template.spec.containers  # type: ignore[attr-defined]
        container = self._get_container(container_name=self.container_name, containers=containers)
        if not container:
            logger.error("Could not get container `%s`", self.container_name)
            return
        if not container.volumeMounts:
            container.volumeMounts = [self.ebpf_volumemount]
        else:
            container.volumeMounts.append(self.ebpf_volumemount)
        if not statefulset.spec.template.spec.volumes:  # type: ignore[attr-defined]
            statefulset.spec.template.spec.volumes = [self.ebpf_volume]  # type: ignore[attr-defined]
        else:
            statefulset.spec.template.spec.volumes.append(self.ebpf_volume)  # type: ignore[attr-defined]
        try:
            self.client.replace(obj=statefulset)
        except ApiError:
            logger.error("Could not replace statefulset `%s`", self.app_name)
            return
        logger.info("Replaced `%s` statefulset", self.app_name)

    @property
    def _pod_name(self) -> str:
        """Name of the unit's pod."""
        return "-".join(self.unit_name.rsplit("/", 1))


class AMFService:
    """Class representing the NGAPP Service for the AMF."""

    def __init__(self, namespace: str, name: str, app_name: str, ngapp_port: int):
        self.client = Client()
        self.namespace = namespace
        self.name = name
        self.app_name = app_name
        self.ngapp_port = ngapp_port

    def is_created(self) -> bool:
        """Check whether load balancer service is created."""
        try:
            self.client.get(Service, name=self.name, namespace=self.namespace)
        except ApiError:
            return False
        return True

    def create(self) -> None:
        """Create NGAPP load balancer service."""
        self.client.apply(
            Service(
                apiVersion="v1",
                kind="Service",
                metadata=ObjectMeta(
                    namespace=self.namespace,
                    name=self.name,
                ),
                spec=ServiceSpec(
                    selector={"app.kubernetes.io/name": self.app_name},
                    ports=[
                        ServicePort(name="ngapp", port=self.ngapp_port, protocol="SCTP"),
                    ],
                    type="LoadBalancer",
                ),
            ),
            field_manager=self.app_name,
        )
        logger.info("Created/asserted existence of external AMF service")

    def get_info(self) -> Tuple[str, str]:
        """Return AMF load balancer service information."""
        service = self.client.get(Service, name=self.name, namespace=self.namespace)
        if not service.status:
            return "", ""
        if not service.status.loadBalancer:
            return "", ""
        if not service.status.loadBalancer.ingress:
            return "", ""
        ip = service.status.loadBalancer.ingress[0].ip
        hostname = service.status.loadBalancer.ingress[0].hostname
        return (
            str(ip) if ip else "",
            str(hostname) if hostname else "",
        )
