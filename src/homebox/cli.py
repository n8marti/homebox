
import argparse
import logging
import sys

from . import BANDWIDTH_THRESHOLD_DEFAULT, http_api
from .bandwidth import DOWNLOAD_THREADS_DEFAULT, get_download_bw


def print_bandwidth():
    parser = argparse.ArgumentParser(prog="homebox-bandwidth")
    parser.add_argument("-i", "--server-id", type=int, default=0, help="set explicit speedtest server ID")
    parser.add_argument("-t", "--threads", type=int, default=DOWNLOAD_THREADS_DEFAULT, help="override default speedtest download threads")
    parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    args = parser.parse_args()

    # Set up logging.
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    logging.basicConfig(format="{levelname}: {message}", style="{", level=level)
    print(get_download_bw(server_id=args.server_id, threads=args.threads))


def set_new_wan_ip():
    parser = argparse.ArgumentParser(prog="homebox-new-wan-ip")
    parser.add_argument("-a", "--apn", help="specify which APN profile to apply")
    parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    args = parser.parse_args()

    # Set up logging.
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    logging.basicConfig(format="{levelname}: {message}", style="{", level=level)

    # Toggle APN to get new IP address.
    print(http_api.get_new_wan_ip(apn=args.apn))


def print_wan_ip():
    parser = argparse.ArgumentParser(prog="homebox-wan-ip")
    parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    args = parser.parse_args()

    # Set up logging.
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    logging.basicConfig(format="{levelname}: {message}", style="{", level=level)

    # Show current WAN IP address.
    print(http_api.get_wan_ip())


def main():
    parser = argparse.ArgumentParser(prog="homebox-verify-connection")
    parser.add_argument("-n", "--new-ip", action="store_true", help="set new IP address and exit")
    parser.add_argument("-s", "--speedtest", action="store_true", help="run speedtest and exit")
    parser.add_argument("-i", "--server-id", type=int, default=0, help="set explicit speedtest server ID")
    parser.add_argument("-m", "--minimum-bandwidth", type=int, default=BANDWIDTH_THRESHOLD_DEFAULT)
    parser.add_argument("-t", "--threads", type=int, default=DOWNLOAD_THREADS_DEFAULT, help="override default speedtest download threads")
    parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    args = parser.parse_args()

    # Set up logging.
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    logging.basicConfig(format="{levelname}: {message}", style="{", level=level)
    # print(logging.root.manager.loggerDict)
    logger = logging.getLogger()

    if args.new_ip:
        # Toggle APN to get new IP address.
        set_new_wan_ip()
        # Check bandwidth afterwards.
        get_download_bw(server_id=args.server_id, threads=args.threads)
        sys.exit()

    # Get current download bandwidth.
    bw = get_download_bw(server_id=args.server_id, threads=args.threads)

    if args.speedtest:
        # Speedtest done; don't consider new IP address.
        sys.exit()

    # Consider new IP address.
    if bw > args.minimum_bandwidth:
        logger.info("Bandwidth is sufficient.")
        sys.exit()

    # Set new IP address.
    set_new_wan_ip()
