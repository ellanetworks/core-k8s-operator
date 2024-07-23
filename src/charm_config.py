# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Config of the Charm."""

import dataclasses
import logging
from ipaddress import IPv4Address, IPv4Network
from typing import List

import ops
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
)

logger = logging.getLogger(__name__)


class CharmConfigInvalidError(Exception):
    """Exception raised when a charm configuration is found to be invalid."""

    def __init__(self, msg: str):
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


def to_kebab(name: str) -> str:
    """Convert a snake_case string to kebab-case."""
    return name.replace("_", "-")


class EllaConfig(BaseModel):
    """Represent Ella operator builtin configuration values."""

    model_config = ConfigDict(alias_generator=to_kebab, use_enum_values=True)

    interfaces: List[str] = ["n3", "n6"]
    logging_level: str = "info"
    gnb_subnet: IPv4Network = IPv4Network("192.168.251.0/24")
    n3_ip: IPv4Address = IPv4Address("192.168.252.3")
    n3_gateway_ip: IPv4Address = IPv4Address("192.168.252.1")
    n6_ip: IPv4Address = IPv4Address("192.168.250.3")
    n6_gateway_ip: IPv4Address = IPv4Address("192.168.250.1")


@dataclasses.dataclass
class CharmConfig:
    """Represent the configuration of the charm."""

    interfaces: List[str]
    logging_level: str
    gnb_subnet: IPv4Network
    n3_ip: IPv4Address
    n3_gateway_ip: IPv4Address
    n6_ip: IPv4Address
    n6_gateway_ip: IPv4Address

    def __init__(self, *, ella_config: EllaConfig):
        """Initialize a new instance of the CharmConfig class.

        Args:
            ella_config: Ella operator configuration.
        """
        self.interfaces = ella_config.interfaces
        self.logging_level = ella_config.logging_level
        self.gnb_subnet = ella_config.gnb_subnet
        self.n3_ip = ella_config.n3_ip
        self.n3_gateway_ip = ella_config.n3_gateway_ip
        self.n6_ip = ella_config.n6_ip
        self.n6_gateway_ip = ella_config.n6_gateway_ip

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
    ) -> "CharmConfig":
        """Initialize a new instance of the CharmState class from the associated charm."""
        try:
            # ignoring because mypy fails with:
            # "has incompatible type "**dict[str, str]"; expected ...""
            interfaces = str(charm.config.get("interfaces", "[n3,n6]"))
            return cls(
                ella_config=EllaConfig(
                    interfaces=interfaces.replace(" ", "")
                    .replace("[", "")
                    .replace("]", "")
                    .split(","),
                    logging_level=str(charm.config.get("logging_level", "info")),
                    gnb_subnet=IPv4Network(charm.config.get("gnb_subnet", "192.168.251.0/24")),
                    n3_ip=IPv4Address(charm.config.get("n3_ip", "192.168.252.3")),
                    n3_gateway_ip=IPv4Address(charm.config.get("n3_gateway_ip", "192.168.252.1")),
                    n6_ip=IPv4Address(charm.config.get("n6_ip", "192.168.250.3")),
                    n6_gateway_ip=IPv4Address(charm.config.get("n6_gateway_ip", "192.168.250.1")),
                )
            )
        except ValidationError as exc:
            error_fields: list = []
            for error in exc.errors():
                if param := error["loc"]:
                    error_fields.extend(param)
                else:
                    value_error_msg: ValueError = error["ctx"]["error"]  # type: ignore
                    error_fields.extend(str(value_error_msg).split())
            error_fields.sort()
            error_field_str = ", ".join(f"'{f}'" for f in error_fields)
            raise CharmConfigInvalidError(
                f"The following configurations are not valid: [{error_field_str}]"
            ) from exc
