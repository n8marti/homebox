import logging
import sys

from speedtest.client import SpeedtestClient
from speedtest.engine.config import ConfigFetchError, get_config
from speedtest.models import RunContext

DOWNLOAD_THREADS_DEFAULT = 1
SERVER_ID_DEFAULT = 0
logger = logging.getLogger()


def as_str(server) -> str:
    return f"{server.name}:{server.sponsor}:{server.id}"


def get_download_bw(
    server_id=SERVER_ID_DEFAULT,
    threads=DOWNLOAD_THREADS_DEFAULT,
) -> int:
    ctx = RunContext
    try:
        ctx.api_config = get_config()
    except ConfigFetchError:
        logger.critical("Failed to fetch config.")
        sys.exit(1)

    ctx.threads = threads  # set manually b/c not getting from args
    client = SpeedtestClient()
    target_servers = client.get_target_servers(ctx.api_config)

    # Determine speedtest server to use.
    server = None
    # Handle passed server ID.
    if server_id > 0:
        for srv in target_servers:
            if int(srv.id) == server_id:
                server = srv

    # Determine nearest server, if needed.
    if server is None:
        logger.info("Selecting nearest Speedtest server...")
        server, _ = client.select_best_server(target_servers)
        # print("Selecting first listed Speedtest server.")
        # server = target_servers[0]

    logger.info(f"Testing download speed from \"{as_str(server)}\"")
    _, bw = client.download(server, ctx)
    bw = round(bw)
    return bw
