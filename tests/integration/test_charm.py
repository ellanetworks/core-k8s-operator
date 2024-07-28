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
DB_CHARM_NAME = "mongodb-k8s"
DB_CHARM_CHANNEL = "6/beta"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, request):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    assert ops_test.model
    charm_path = Path(request.config.getoption("--charm_path")).resolve()
    resources = {"ella-image": METADATA["resources"]["ella-image"]["upstream-source"]}

    await ops_test.model.deploy(
        entity_url=charm_path, resources=resources, application_name=APP_NAME
    )
    await ops_test.model.deploy(
        DB_CHARM_NAME,
        application_name=DB_CHARM_NAME,
        channel=DB_CHARM_CHANNEL,
    )

    await ops_test.model.integrate(relation1=f"{APP_NAME}:database", relation2=f"{DB_CHARM_NAME}")

    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)
