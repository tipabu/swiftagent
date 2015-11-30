from __future__ import print_function

import argparse
import logging
import os
import pprint

from swiftagent.agent import client
from swiftagent import auth
from swiftagent import config
from swiftagent import models


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true',
                        help='include debugging information')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('url', default=None, nargs='?',
                       help='the url of the Swift cluster '
                            'whose info you want to get')
    group.add_argument('--auth', help='the auth endpoint to use')
    args = parser.parse_args(args[1:])

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    if args.url:
        url = args.url
    else:
        conf = config.SwiftConfig()
        authenticator = args.auth or conf.default_auth
        if not authenticator:
            logging.error('No auth endpoint specified, and no default defined')
            return

        if client.can_use_swift_agent():
            dummy, (url, dummy) = client.get_auth_with_unlock(authenticator)
        else:
            url, dummy = conf.get_auth(authenticator).get_credentials()

    if client.can_use_swift_agent():
        sock = os.environ[client.SOCKET_ENV_VAR]
        with client.SwiftAgentClient(sock) as agent_client:
            info = agent_client.info(url)
    else:
        info = models.Cluster(auth.noauth({'storage_url': url})).info()
    pprint.pprint(info)
