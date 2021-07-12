#!/usr/bin/env python3
"""
Noia platform agent.
"""

__author__ = "SYNTROPY Network"
__version__ = "0.0.84"
__license__ = "MIT"

import os
import argparse
import atexit
import logging

from platform_agent.config.logger import configure_logger
from platform_agent.config.settings import Config, AGENT_PATH_TMP, ConfigException
from platform_agent.agent_websocket import WebSocketClient

from pyroute2 import WireGuard

logger = logging.getLogger()

def exit_handler():
    from pathlib import Path
    import shutil

    dirpath = Path(AGENT_PATH_TMP)
    if dirpath.exists() and dirpath.is_dir():
        shutil.rmtree(dirpath)


atexit.register(exit_handler)


def main(args=None):
    """ This is executed when run from the command line """

    try:
        WireGuard()
    except:
        # Wireguard module load failed
        pass

    parser = argparse.ArgumentParser()

    # Required positional argument
    parser.add_argument("run", help="Required parameter to start agent")

    # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity (-v, -vv, etc)")

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__))

    args = parser.parse_args()
    agent(args)


def agent(args):
    """ Main entry point of the app """
    if args.run:
        # Retrieving settings from config on start
        try:
            Config()
        except ConfigException as e:
            logger.error(f"[CONFIG]: {e}")
            return

        # Configuring logger globally
        configure_logger()

        # Initiating WS client
        client = WebSocketClient(
            os.environ.get('SYNTROPY_CONTROLLER_URL', 'controller-prod-platform-agents.syntropystack.com'),
            os.environ['SYNTROPY_AGENT_TOKEN']
        )

        # Starting WS client main thread
        client.start()


if __name__ == "__main__":
    """ This is executed when run from the command line """
    main()
