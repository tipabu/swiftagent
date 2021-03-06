from __future__ import print_function

import argparse
import getpass
import logging
import os

from swiftagent.agent import client
from swiftagent.auth import agent
from swiftagent.auth import base
from swiftagent import config
from swiftagent import io
from swiftagent import models


def main(args):
    '''Get a storage URL and auth token for a Swift cluster.

    If a swift-agent server seems to be running, that will be used
    to authenticate.
    '''
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        '--debug', action='store_true',
        help='include debugging information')
    parser.add_argument(
        'auth', default=None, nargs='?',
        help='the auth endpoint to use')
    parser.add_argument(
        '--verify', action='store_true', default=None,
        help='verify the token is still valid if received from '
             'a swift-agent server')
    parser.add_argument(
        '--no-verify', action='store_false', dest='verify',
        help='skip token verification')
    args = parser.parse_args(args[1:])

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    conf = config.SwiftConfig()

    auth = args.auth or conf.default_auth
    if not auth:
        logging.error('No auth endpoint specified, and no default defined')
        return

    if client.can_use_swift_agent():
        authenticator = agent.AgentAuthenticator({'auth_name': auth})
    else:
        authenticator = conf.get_auth(auth)
    storage_url, token, expiry = authenticator.get_credentials()

    if args.verify is None:
        verify = conf.get_default_verify(auth)
    else:
        verify = args.verify

    if verify and client.can_use_swift_agent():
        try:
            models.Cluster(authenticator).default_account.info()
        except base.Unauthorized:
            if authenticator.ever_prompted:
                raise

            password = getpass.getpass()
            sock = os.environ[client.SOCKET_ENV_VAR]
            with client.SwiftAgentClient(sock) as agent_client:
                agent_client.unlock(auth, password)
                storage_url, token, expiry = agent_client.auth(auth)

    io.export({'OS_STORAGE_URL': storage_url,
               'OS_AUTH_TOKEN': token,
               'OS_AUTH_TOKEN_EXPIRES': expiry})
