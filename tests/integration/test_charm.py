#!/usr/bin/env python3
# Copyright 2024 Guillaume Belanger
# See LICENSE file for licensing details.

import logging
import time
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

from tests.integration.ella_helper import Ella
from tests.integration.juju_helper import get_unit_address, juju_run_action

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
DB_CHARM_NAME = "mongodb-k8s"
GNBSIM_CHARM_NAME = "sdcore-gnbsim-k8s"
GNBSIM_CHANNEL = "1.5/edge"
DB_CHARM_CHANNEL = "6/beta"
TEST_IMSI = "208930100007487"
TEST_NETWORK_SLICE_NAME = "default"
TEST_DEVICE_GROUP_NAME = "default-default"


@pytest.fixture(scope="module")
@pytest.mark.abort_on_fail
def configure_ella(ops_test: OpsTest):
    """Configure Ella.

    Configuration includes:
    - subscriber creation
    - device group creation
    - network slice creation
    """
    assert ops_test.model
    ella_ip_address = get_unit_address(
        model_name=ops_test.model.name,
        application_name=APP_NAME,
        unit_number=0,
    )
    ella_client = Ella(url=f"http://{ella_ip_address}:5000")
    ella_client.create_subscriber(TEST_IMSI)
    ella_client.create_device_group(TEST_DEVICE_GROUP_NAME, [TEST_IMSI])
    ella_client.create_network_slice(TEST_NETWORK_SLICE_NAME, [TEST_DEVICE_GROUP_NAME])
    # 5 seconds for the config to propagate
    time.sleep(5)


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
        entity_url=DB_CHARM_NAME,
        application_name=DB_CHARM_NAME,
        channel=DB_CHARM_CHANNEL,
    )
    await ops_test.model.deploy(
        entity_url=GNBSIM_CHARM_NAME,
        application_name=GNBSIM_CHARM_NAME,
        channel=GNBSIM_CHANNEL,
    )

    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:database", relation2=f"{DB_CHARM_NAME}:database"
    )
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:fiveg-n2", relation2=f"{GNBSIM_CHARM_NAME}:fiveg-n2"
    )
    await ops_test.model.integrate(
        relation1=f"{APP_NAME}:fiveg_gnb_identity",
        relation2=f"{GNBSIM_CHARM_NAME}:fiveg_gnb_identity",
    )

    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="active", timeout=1000)


@pytest.mark.abort_on_fail
async def test_given_ella_and_gnbsim_deployed_when_start_simulation_then_simulation_success_status_is_true(  # noqa: E501
    ops_test: OpsTest, configure_ella
):
    assert ops_test.model
    for _ in range(5):
        action_output = juju_run_action(
            model_name=ops_test.model.name,
            application_name=GNBSIM_CHARM_NAME,
            unit_number=0,
            action_name="start-simulation",
            timeout=6 * 60,
        )
        try:
            assert action_output["success"] == "true"
            return
        except AssertionError:
            continue
    assert False
