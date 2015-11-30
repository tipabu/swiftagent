from __future__ import unicode_literals
import contextlib
import json

from swiftagent.agent import comm
from swiftagent import auth
from swiftagent.auth import base
from swiftagent import config
from swiftagent import models


class SwiftAgentServer(comm.LineOrientedUnixServer):
    def __init__(self, socket_address):
        super(SwiftAgentServer, self).__init__(socket_address)
        self.cache = {
            'passwords': {},
            'authenticators': {},
            'info': {},
        }
        self.reload()

    def reload(self):
        '''Reload the backing SwiftConfig.'''
        self.conf = config.SwiftConfig()

    def get_authenticator(self, auth_config):
        '''Get an authenticator from an auth config.

        :param auth_config: the auth config to use
        '''
        authenticator = self.cache['authenticators'].get(auth_config)
        if not authenticator:
            password = self.cache['passwords'].get(auth_config)
            authenticator = self.cache['authenticators'][auth_config] = \
                self.conf.get_auth(auth_config, password)
        return authenticator

    def get_info(self, url):
        '''Get the capabilities of a Swift cluster.

        :param url: the absolute URL for the Swift cluster
        :returns: a dict containing the (possibly cached) result
                  of the /info request
        '''
        info = self.cache['info'].get(config.scheme_netloc_only(url))
        if not info:
            cluster = models.Cluster(auth.noauth({'storage_url': url}))
            info = self.cache['info'][url] = cluster.info()
        return info

    def purge(self, auth_config_or_url):
        '''Clear the caches for a given auth config or URL.'''
        self.cache['passwords'].pop(auth_config_or_url, None)
        self.cache['authenticators'].pop(auth_config_or_url, None)
        self.cache['info'].pop(auth_config_or_url, None)

    @contextlib.contextmanager
    def purge_on_error(self, auth_config, exc_types=(Exception,)):
        '''Context manager to purge an auth config on certain exceptions.

        :param auth_config: the auth config to purge
        :param exc_types:   the type or types of exceptions to trigger a purge
        '''
        try:
            yield
        except Exception as exc:
            if isinstance(exc, exc_types):
                self.purge(auth_config)
            raise

    def handle_reload(self, dummy):
        '''Socket command: reload the server's SwiftConfig.

        This may be used to learn about new auth endpoints.

        :param dummy: (ignored)
        '''
        self.reload()
        return 'reloaded'

    def handle_unlock(self, data):
        '''Socket command: unlock a particular auth config.

        :param data: a string of the form "[auth_config] [password]"
        '''
        auth_config, dummy, password = data.partition(' ')
        self.cache['passwords'][auth_config] = password
        self.cache['authenticators'].pop(auth_config, None)
        with self.purge_on_error(auth_config):
            self.get_authenticator(auth_config).get_credentials()
        return 'unlocked'

    def handle_purge(self, data):
        '''Socket command: purge a particular auth config from the caches.

        :param data: a string of the form "[auth_config]"
        '''
        self.purge(data)
        return 'purged'

    def handle_auth(self, data):
        '''Socket command: get the credentials for an auth config.

        :param data: a string of the form "[auth_config]"
        :returns: a string of the form "auth [url] [token]"
        '''
        with self.purge_on_error(data, base.Unauthorized):
            url, token = self.get_authenticator(data).get_credentials()
        return 'auth %s %s' % (url, token)

    def handle_reauth(self, data):
        '''Socket command: refresh the credentials for an auth config.

        :param data: a string of the form "[auth_config]"
        :returns: a string of the form "auth [url] [token]"
        '''
        url, token = self.get_authenticator(data).reauth()
        return 'auth %s %s' % (url, token)

    def handle_info(self, data):
        '''Socket command: get the capabilities of a Swift cluster.

        :param data: a string of the form "[cluster_url]"
        :returns: a single-line JSON representation of the /info response
        '''
        return json.dumps(self.get_info(data))

    def handle_reinfo(self, data):
        '''Socket command: get the fresh capabilities of a Swift cluster.

        :param data: a string of the form "[cluster_url]"
        :returns: a single-line JSON representation of the /info response
        '''
        self.purge(data)
        return json.dumps(self.get_info(data))
