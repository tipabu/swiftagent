'''
Authenticator module for Ye Olde v1 auth.
'''
import requests

from swiftagent.auth import base
from swiftagent import opt


class V1Authenticator(base.BaseAuthenticator):
    '''Authenticator for auth v1 endpoints.'''
    @classmethod
    def get_opts(cls):
        return opt.AllOf(
            opt.UrlOpt('auth_url'),
            opt.StrOpt('username'),
            opt.StrOpt('password'),
        )

    def reauth(self):
        resp = requests.get(
            self.conf['auth_url'],
            headers={
                'X-Auth-User': self.conf['username'],
                'X-Auth_Key': self.conf['password'],
                'Content-Length': 0,
            },
            timeout=10,
            verify=not (self.check_insecure and
                        self.check_insecure(self.conf['auth_url'])))
        if resp.status_code // 100 != 2:
            raise base.error_from_response(resp, self)
        missing_headers = [h for h in ('X-Auth-Token', 'X-Storage-Url')
                           if h not in resp.headers]
        if missing_headers:
            raise base.AuthError(
                self,
                'Missing header(s): %s' % ', '.join(missing_headers))
        return resp.headers['X-Storage-Url'], resp.headers['X-Auth-Token']
