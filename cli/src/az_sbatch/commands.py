from knack.commands import CLICommandsLoader, CommandGroup
from knack.arguments import ArgumentsContext
from knack.help_files import helps
from knack.log import get_logger
from azure.batch import models

from . import utils, azfinsim, tools_json

log = get_logger(__name__)


class CommandsLoader(CLICommandsLoader):
    """Commands loader for the sbatch module."""

    def load_command_table(self, args):
        with CommandGroup(self, "", "az_sbatch.commands#{}") as g:
            g.command("show", "show")
        with CommandGroup(self, "pool", "az_sbatch.commands#pool_{}") as g:
            g.command("list", "list")
            g.command("resize", "resize")
            g.command("show", "show")
        azfinsim.populate_commands(self)
        tools_json.populate_commands(self)
        return super().load_command_table(args)

    def load_arguments(self, command):
        with ArgumentsContext(self, "") as c:
            c.argument(
                "subscription_id",
                options_list=["--subscription-id", "-s"],
                help="The subscription ID.",
                arg_group="Deployment",
            )
            c.argument(
                "resource_group_name",
                options_list=["--resource-group-name", "-g"],
                help="The name of the resource group.",
                arg_group="Deployment",
            )
        with ArgumentsContext(self, "show") as c:
            c.argument(
                "only_validate",
                options_list=["--only-validate"],
                help="Only validate the resource group and subscription ID.",
                action="store_true",
            )
        with ArgumentsContext(self, "pool") as c:
            c.argument(
                "pool_id",
                options_list=["--pool-id", "-p"],
                help="The ID of the pool to resize.",
            )
            c.argument(
                "no_wait",
                options_list=["--no-wait"],
                help="Do not wait for the operation to complete.",
                action="store_true",
            )
            c.argument(
                "await_compute_nodes",
                options_list=["--await-compute-nodes"],
                help="Wait for the compute nodes to be ready; ignored if `--no-wait` is specified.",
                action="store_true",
            )
            c.argument(
                "target_dedicated_nodes",
                options_list=["--target-dedicated-nodes", "-d"],
                help="The target dedicated node count for the pool.",
                type=int,
            )
            c.argument(
                "target_spot_nodes",
                options_list=["--target-spot-nodes", "-l"],
                help="The target spot node count for the pool.",
                type=int,
            )
        azfinsim.populate_arguments(self)
        tools_json.populate_arguments(self)
        return super().load_arguments(command)


helps[
    "show"
] = r"""
    type: command
    short-summary: Show the configuration of the sbatch deployment.
    long-summary: |
        Shows the configuration details of the sbatch deployment. This is useful
        to get access to various resources and endpoints for resources that
        are used for management and trying of the demos.
"""


def show(resource_group_name, subscription_id, only_validate=False):
    log.debug(f"subscription_id: {subscription_id}")
    log.debug(f"resource_group_name: {resource_group_name}")
    credentials = utils.get_credentials()
    subscription_id = utils.get_subscription_id(subscription_id)
    log.debug(f"subscription_id (x-formed): {subscription_id}")

    # lets locate various components of the deployment.
    if not utils.validate_resource_group(
        credentials, subscription_id, resource_group_name
    ):
        log.critical("Resource group not found. Did you create the deployment?")
        return {"status": False} if only_validate else None

    if only_validate:
        return {"status": True}

    config = {}
    config["acr_name"] = utils.locate_acr(
        credentials, subscription_id, resource_group_name
    )
    config["batch_endpoint"] = utils.locate_batch_endpoint(
        credentials, subscription_id, resource_group_name
    )
    return config


helps[
    "pool"
] = r"""
    type: group
    short-summary: Manage batch pools.
    long-summary: |
        Commands to manage batch pools.
"""

helps[
    "pool list"
] = r"""
    type: command
    short-summary: List the pools in the batch account.
    long-summary: |
        Lists the pools in the batch account.
"""


def pool_list(resource_group_name, subscription_id):
    log.debug(f"subscription_id: {subscription_id}")
    log.debug(f"resource_group_name: {resource_group_name}")
    credentials = utils.get_credentials()
    subscription_id = utils.get_subscription_id(subscription_id)
    log.debug(f"subscription_id (x-formed): {subscription_id}")

    # lets locate various components of the deployment.
    if not utils.validate_resource_group(
        credentials, subscription_id, resource_group_name
    ):
        log.critical("Resource group not found. Did you create the deployment?")
        return

    bclient = utils.get_batch_client(credentials, subscription_id, resource_group_name)
    pools = bclient.pool.list()
    return [p for p in pools]


helps[
    "pool show"
] = r"""
    type: command
    short-summary: Shows summary information for a specific pool in the batch account.
    long-summary: |
        Shows summary information for a specific pool in the batch account.
"""

def pool_show(resource_group_name, subscription_id, pool_id):
    log.debug(f"subscription_id: {subscription_id}")
    log.debug(f"resource_group_name: {resource_group_name}")
    log.debug(f"pool_id: {pool_id}")
    credentials = utils.get_credentials()
    subscription_id = utils.get_subscription_id(subscription_id)
    log.debug(f"subscription_id (x-formed): {subscription_id}")

    # lets locate various components of the deployment.
    if not utils.validate_resource_group(
        credentials, subscription_id, resource_group_name
    ):
        log.critical("Resource group not found. Did you create the deployment?")
        return

    bclient = utils.get_batch_client(credentials, subscription_id, resource_group_name)
    return bclient.pool.get(pool_id)


helps[
    "pool resize"
] = r"""
    type: command
    short-summary: Resize the pool.
"""


def pool_resize(
    resource_group_name,
    subscription_id,
    pool_id,
    target_dedicated_nodes=None,
    target_spot_nodes=None,
    await_compute_nodes=False,
    no_wait=False,
):
    log.debug(f"subscription_id: {subscription_id}")
    log.debug(f"resource_group_name: {resource_group_name}")
    log.debug(f"pool_id: {pool_id}")
    log.debug(f"target_dedicated_nodes: {target_dedicated_nodes}")
    log.debug(f"target_spot_nodes: {target_spot_nodes}")
    log.debug(f"no_wait: {no_wait}")
    if target_dedicated_nodes is None and target_spot_nodes is None:
        log.critical(
            "Either target_dedicated_nodes or target_spot_nodes must be specified."
        )
        return
    credentials = utils.get_credentials()
    subscription_id = utils.get_subscription_id(subscription_id)

    bclient = utils.get_batch_client(credentials, subscription_id, resource_group_name)
    pool_info = bclient.pool.get(pool_id)
    if pool_info is None:
        log.critical(f"Pool {pool_id} not found.")
        return
    if pool_info.allocation_state == "resizing":
        log.critical(f"Pool {pool_id} is already resizing.")
        return
    if pool_info.allocation_state == "stopping":
        log.critical(f"Pool {pool_id} is already stopping.")
        return

    log.debug(f"current_dedicated_nodes: {pool_info.current_dedicated_nodes}")
    log.debug(f"current_spot_nodes: {pool_info.current_low_priority_nodes}")
    bclient.pool.resize(
        pool_id,
        models.PoolResizeParameter(
            target_dedicated_nodes=target_dedicated_nodes,
            target_low_priority_nodes=target_spot_nodes,
        ),
    )
    if not no_wait:
        log.info("awaiting pool resize")
        rc = utils.wait_until(lambda: bclient.pool.get(pool_id).allocation_state == "steady")
        if rc is utils.WAIT_UNTIL_RC.TIMEOUT:
            log.error("Timed out waiting for pool resize.")
            return {}
        if rc is utils.WAIT_UNTIL_RC.FAILURE:
            log.error("Pool resize failed.")
            return {}
        log.info("Pool resize is complete.")

    def verify():
        pool_config = bclient.pool.get(pool_id)
        if pool_config.resize_errors and len(pool_config.resize_errors) > 0:
            log.error(f"Pool {pool_id} resize failed.")
            msg = "\n".join([f"  {e.code}: {e.message}" for e in pool_config.resize_errors])
            log.error(f"Resize errors: \n{msg}")
            return utils.WAIT_UNTIL_CALLBACK_RC.CANCEL_WAIT # abort
        count = 0
        for cn in bclient.compute_node.list(pool_id):
            lc_state = cn.state.lower()
            if lc_state in ["idle", "running"]:
                count += 1
            elif lc_state in ["unusable", "starttaskfailed", "offline", "unknown"]:
                log.error(f"Compute node {cn.id} is in {cn.state} state.")
                return utils.WAIT_UNTIL_CALLBACK_RC.CANCEL_WAIT # abort
        if count == (target_dedicated_nodes or 0) + (target_spot_nodes or 0):
            return utils.WAIT_UNTIL_CALLBACK_RC.SUCCESS # done
        return utils.WAIT_UNTIL_CALLBACK_RC.CONTINUE_WAIT # continue waiting

    if no_wait and await_compute_nodes:
        log.warn(
            "--await-compute-nodes does not make sense when --no-wait is specified. ignoring"
        )
    elif await_compute_nodes:
        # pool allocation state change is not adequate; we must wait till compute nodes
        # are available
        log.info("awaiting compute nodes startup + init")
        rc = utils.wait_until(lambda: verify())
        if rc is utils.WAIT_UNTIL_RC.TIMEOUT:
            log.error("Timed out waiting for compute nodes to be ready.")
            return {}
        if rc is utils.WAIT_UNTIL_RC.FAILURE:
            log.error("Compute nodes failed to start.")
            return {}
        log.info("Compute nodes are ready.")
    pool_info = bclient.pool.get(pool_id)
    return {
        "current_dedicated_nodes": pool_info.current_dedicated_nodes,
        "current_low_priority_nodes": pool_info.current_low_priority_nodes,
    }
