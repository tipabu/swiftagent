'''
Authenticator module for when you don't really have credentials,
just a storage URL and maybe a token.
'''
from swiftagent.auth import base
from swiftagent import opt


class TokenAuthenticator(base.BaseAuthenticator):
    '''A token-based authenticator.'''
    requires_password = False

    @classmethod
    def get_opts(cls):
        return opt.AllOf(
            opt.UrlOpt('storage_url'),
            opt.Maybe(opt.StrOpt('auth_token')),
        )

    def reauth(self):
        return self.conf['storage_url'], self.conf.get('auth_token', '')


class NoAuthAuthenticator(TokenAuthenticator):
    '''Authenticator that *only* has a storage URL, not even a token.'''
    @classmethod
    def get_opts(cls):
        return opt.UrlOpt('storage_url')
