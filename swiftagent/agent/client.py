'''
Tools for interacting with a swift-agent server.
'''
import getpass
import json
import os
import stat
import sys

from swiftagent.agent import comm
from swiftagent.auth import base


PROCESS_ID_ENV_VAR = 'SWIFT_AGENT_PID'
SOCKET_ENV_VAR = 'SWIFT_AGENT_SOCK'


class SwiftAgentClientError(Exception):
    '''Class for some type of swift-agent error.'''
    pass


def raise_on_error(result, source):
    '''Check a swift-agent reponse for errors.

    :param result: the response from swift-agent
    :param source: the source that should be used when raising AuthErrors
    :raises: Unauthorized,
             Forbidden,
             PasswordRequired, or
             SwiftAgentClientError
    '''
    if not result.startswith('ERROR '):
        return
    result = result[6:]
    if result.startswith('Unauthorized('):
        raise base.Unauthorized(source)
    if result.startswith('Forbidden('):
        raise base.Forbidden(source)
    if result.startswith('PasswordRequired('):
        raise base.PasswordRequired(source)
    raise SwiftAgentClientError(result)


class SwiftAgentClient(comm.LineOrientedUnixClient):
    '''Unix Domain Socket client to interact with swift-agent.

    This is necessarily ephemeral. You shouldn't use the same client for both
    getting session details and unlocking the authenticator when that fails,
    for example; the connection will almost certainly time out while waiting
    for user input.
    '''
    def reload(self):
        '''Reload the swift config server-side.

        :returns: True if the server acknowledges a reload, False otherwise
        :raises: any of the possibilities from raise_on_error
        '''
        result = self.send_command('reload')
        raise_on_error(result, self)
        return result == 'reloaded'

    def auth(self, auth_name):
        '''Fetch the details of an authenticated session from swift-agent.

        :param auth_name: the name of the auth config to use
        :returns: a tuple of (storage_url, auth_token)
        :raises: any of the possibilities from raise_on_error
        '''
        result = self.send_command('auth %s' % auth_name)
        raise_on_error(result, self)
        if not result.startswith('auth '):
            raise base.AuthError(self, 'Unexpected response: %s' % result)
        return result[5:].split(' ', 1)

    def reauth(self, auth_name):
        '''Fetch the details of a freshly auth'ed session from swift-agent.

        :param auth_name: the name of the auth config to use
        :returns: a tuple of (storage_url, auth_token)
        :raises: any of the possibilities from raise_on_error
        '''
        result = self.send_command('reauth %s' % auth_name)
        raise_on_error(result, self)
        if not result.startswith('auth '):
            raise base.AuthError(self, 'Unexpected response: %s' % result)
        return result[5:].split(' ', 1)

    def unlock(self, auth_name, password):
        '''Try to unlock an authenticated session.

        :param auth_name: the name of the auth config to use
        :param password: the password to use to unlock it
        :returns: True if the server acknowledges an unlock, False otherwise
        :raises: any of the possibilities from raise_on_error
        '''
        result = self.send_command('unlock %s %s' % (auth_name, password))
        raise_on_error(result, self)
        return result == 'unlocked'

    def purge(self, auth_name):
        '''Purge the details of an authenticated session from swift-agent.

        :param auth_name: the name of the auth config to use
        :returns: True if the server acknowledges a purge, False otherwise
        :raises: any of the possibilities from raise_on_error
        '''
        result = self.send_command('purge %s' % auth_name)
        raise_on_error(result, self)
        return result == 'purged'

    def info(self, url):
        '''Fetch the capabilities of a Swift server.

        :param url: the absolute URL for the server
        :returns: a dict containing the result of a /info request
        :raises: any of the possibilities from raise_on_error
        '''
        result = self.send_command('info %s' % url)
        raise_on_error(result, self)
        return json.loads(result)

    def reinfo(self, url):
        '''Fetch the fresh capabilities of a Swift server.

        :param url: the absolute URL for the server
        :returns: a dict containing the result of a fresh /info request
        :raises: any of the possibilities from raise_on_error
        '''
        result = self.send_command('reinfo %s' % url)
        raise_on_error(result, self)
        return json.loads(result)


def can_use_swift_agent():
    '''Check whether it's worth trying to connect to a swift-agent server.'''
    if SOCKET_ENV_VAR not in os.environ:
        return False
    try:
        mode = os.stat(os.environ[SOCKET_ENV_VAR]).st_mode
    except OSError:
        return False
    return stat.S_ISSOCK(mode)


def get_auth_with_unlock(auth_name, reauth=False):
    '''Fetch the details of an auth'ed session from swift-agent.

    If the authenticator is hasn't been unlocked and we have an
    interactive shell, prompt to unlock it.

    :param auth_name: the name of the auth config to use
    :returns: a tuple of (prompted_for_password, (storage_url, auth_token))
    :raises: any of the possibilities from raise_on_error
    '''
    def auth_fn():
        if reauth:
            return client.reauth(auth_name)
        else:
            return client.auth(auth_name)

    try:
        with SwiftAgentClient(os.environ[SOCKET_ENV_VAR]) as client:
            return False, auth_fn()
    except base.PasswordRequired:
        if not sys.stdin.isatty():
            raise
        password = getpass.getpass()
        with SwiftAgentClient(os.environ[SOCKET_ENV_VAR]) as client:
            client.unlock(auth_name, password)
            return True, auth_fn()
