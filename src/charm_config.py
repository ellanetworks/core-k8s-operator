# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

"""Config of the Charm."""

import dataclasses
import logging

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

    logging_level: str = "info"
    n2_ip: str = "192.168.253.3/24"
    n3_ip: str = "192.168.252.3/24"
    n6_ip: str = "192.168.250.3/24"


@dataclasses.dataclass
class CharmConfig:
    """Represent the configuration of the charm."""

    logging_level: str
    n2_ip: str
    n3_ip: str
    n6_ip: str

    def __init__(self, *, ella_config: EllaConfig):
        """Initialize a new instance of the CharmConfig class.

        Args:
            ella_config: Ella operator configuration.
        """
        self.logging_level = ella_config.logging_level
        self.n2_ip = ella_config.n2_ip
        self.n3_ip = ella_config.n3_ip
        self.n6_ip = ella_config.n6_ip

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
    ) -> "CharmConfig":
        """Initialize a new instance of the CharmState class from the associated charm."""
        try:
            # ignoring because mypy fails with:
            # "has incompatible type "**dict[str, str]"; expected ...""
            return cls(
                ella_config=EllaConfig(
                    logging_level=str(charm.config.get("logging_level", "info")),
                    n2_ip=charm.config.get("n2-ip", "192.168.253.3/24"),
                    n3_ip=charm.config.get("n3-ip", "192.168.252.3/24"),
                    n6_ip=charm.config.get("n6-ip", "192.168.250.3/24"),
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
