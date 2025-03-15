#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, request):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    assert ops_test.model
    charm_path = Path(request.config.getoption("--charm_path")).resolve()
    resources = {"core-image": METADATA["resources"]["core-image"]["upstream-source"]}

    await ops_test.model.deploy(
        entity_url=charm_path,
        resources=resources,
        application_name=APP_NAME,
        trust=True,
    )

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME],
        status="active",
        timeout=1000,
    )
