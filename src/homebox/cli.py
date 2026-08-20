
import argparse
import logging
import sys

from . import __version__, http_api
from .bandwidth import DOWNLOAD_THREADS_DEFAULT, get_download_bw
try:
    from .gui import run_gui
except ModuleNotFoundError:
    def run_gui(args):
        print("WARNING: Tkinter not installed; GUI not available")


def print_bandwidth(args):
    print(get_download_bw(server_id=args.server_id, threads=args.threads))


def print_wan_ip(args):  # args is needed for compatibility with other funcs
    print(http_api.get_wan_ip())


def set_new_wan_ip(args):
    print(http_api.get_wan_ip(apn=args.apn_profile, new=True))


def main():
    # Handle arguments.
    parser = argparse.ArgumentParser(prog="homeboxctl")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers()
    # Define bandwidth subcommand.
    bw_parser = subparsers.add_parser("bandwidth", help="get current download bandwidth")
    bw_parser.add_argument("-i", "--server-id", type=int, default=0, help="set explicit speedtest server ID")
    bw_parser.add_argument("-t", "--threads", type=int, default=DOWNLOAD_THREADS_DEFAULT, help="override default speedtest download threads")
    bw_parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    bw_parser.set_defaults(func=print_bandwidth)
    # Define wan-ip subcommand.
    ip_parser = subparsers.add_parser("wan-ip", help="get WAN IP address")
    ip_parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    ip_parser.set_defaults(func=print_wan_ip)
    # Define new-wan-ip subcommand.
    newip_parser = subparsers.add_parser("new-wan-ip", help="reset WAN IP address")
    newip_parser.add_argument("-a", "--apn-profile", help="specify which APN profile to apply")
    newip_parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    newip_parser.set_defaults(func=set_new_wan_ip)
    # Define GUI parser.
    gui_parser = subparsers.add_parser("gui", help="run window app")
    gui_parser.add_argument("-v", "--verbose", action="store_true", help="use verbose logging")
    gui_parser.set_defaults(func=run_gui)
    # Parse args.
    args = parser.parse_args()
    if not hasattr(args, "func"):
        # A subcommand is required.
        parser.print_help()
        sys.exit(1)

    # Set up logging.
    log_level = logging.INFO
    if hasattr(args, "verbose") and args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(format="{levelname}: {message}", style="{", level=log_level)

    # Run subcommand.
    args.func(args)
