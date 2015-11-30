import getpass
import importlib
import logging
import os
import sys

from six.moves import configparser
from six.moves import urllib

from swiftagent.auth import base


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def scheme_netloc_only(url):
    '''Given a URL, return just the scheme and netloc part of it.

    :param url: the URL to parse
    :raises ValueError: if ``url`` is not an absolute url
    '''
    scheme_netloc = urllib.parse.urlparse(url)[:2]
    if not all(scheme_netloc):
        raise ValueError('Expected an absolute URL')
    # apparently, pylint thinks six.moves...urlunparse takes no arguments?
    # pylint: disable=too-many-function-args
    return urllib.parse.urlunparse(scheme_netloc + ('', ) * 4)


def _with_default(name):
    wrapped_fn = getattr(configparser.RawConfigParser, name)

    def wrapper(self, section, option, default=None):
        '''Get the value associated with an option, or a default.

        :param section: the section from which to get the value
        :param option: the option name to get
        :param default: the default value to return if ``option``
                        does not exist
        :raises configparser.NoSectionError: if ``section`` does not exist
        '''
        if self.has_option(section, option):
            return wrapped_fn(self, section, option)
        else:
            return default
    return wrapper


class DefaultingConfigParser(configparser.RawConfigParser):
    '''Subclass of a RawConfigParser that simplifies setting defaults.'''
    get = _with_default('get')
    getboolean = _with_default('getboolean')


class SwiftConfig(object):
    '''Configuration object to manage access to Swift clusters.

    The following configs are read (from lowest to highest priority):

      * /etc/swiftagent.conf
      * ${HOME}/.swiftagent.conf
      * ${PWD}/swiftagent.conf
      * ${SWIFT_AGENT_CONF}

    See also: etc/swiftagent.conf-example
    '''
    def __init__(self):
        self.conf = DefaultingConfigParser()
        configs = self.conf.read([
            '/etc/swiftagent.conf',
            os.path.expanduser('~/.swiftagent.conf'),
            'swiftagent.conf',
        ])
        if 'SWIFT_AGENT_CONF' in os.environ:
            configs.extend(self.conf.read([os.environ['SWIFT_AGENT_CONF']]))
        LOGGER.info('Read configs: %r', configs)

        if self.conf.has_section('insecure'):
            self.insecure_servers = self.conf.get('insecure', 'servers', '')
            self.insecure_auth = self.conf.get('insecure', 'auth', '')
        else:
            self.insecure_servers = ''
            self.insecure_auth = ''
        self.insecure_servers = {scheme_netloc_only(server)
                                 for server in self.insecure_servers.split()}
        self.insecure_auth = self.insecure_auth.split()

    def check_insecure(self, url):
        '''Check whether a URL should be considered "insecure".

        If so, assume SSL certificate validation should be disabled.
        '''
        return scheme_netloc_only(url) in self.insecure_servers

    @property
    def default_auth(self):
        '''Get the default auth config that should be used.'''
        auth = self.conf.defaults().get('auth')
        if auth is None and len(self.available_auths) == 1:
            auth = self.available_auths[0]
        return auth

    def get_default_verify(self, auth_name):
        auth_section = 'auth:%s' % auth_name
        return self.conf.getboolean(auth_section, 'verify', True)

    def get_auth(self, auth_name, password=None):
        '''Get an authenticator for a given auth config.'''
        auth_section = 'auth:%s' % auth_name
        use_line = self.conf.get(auth_section, 'use', 'swiftagent.auth:v3')
        module, delim, cls = use_line.partition(':')
        if not (module and delim and cls):
            raise ValueError("'use' must be of the form module:class")
        module = importlib.import_module(module)
        cls = getattr(module, cls)

        auth_config = dict(self.conf.items(auth_section))
        LOGGER.debug('Using auth config %r', auth_config)
        if cls.requires_password:
            if 'password' in auth_config:
                if password is None and auth_name in self.insecure_auth:
                    password = auth_config['password']
                else:
                    LOGGER.warning('Ignoring password from config for auth %s',
                                   auth_name)
            if password is None and sys.stdin.isatty():
                password = getpass.getpass()
            if password is None:
                raise base.PasswordRequired(self)
            auth_config['password'] = password
        return cls(auth_config, self.check_insecure)

    @property
    def available_auths(self):
        '''Get a mapping of auth configs to their auth URLs.'''
        return {s[5:]: self.conf.get(s, 'auth_url')
                for s in self.conf.sections() if s.startswith('auth:')}
