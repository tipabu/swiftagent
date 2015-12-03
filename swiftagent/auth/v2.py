'''
Authenticator module for Ye Olde v1 auth.
'''
import logging
import time

from swiftagent.auth import base
from swiftagent import opt


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class V2Authenticator(base.BaseAuthenticator):
    '''Authenticator for auth v2 endpoints.'''
    @classmethod
    def get_opts(cls):
        return opt.AllOf(
            opt.UrlOpt('auth_url'),
            opt.StrOpt('username'),
            opt.StrOpt('password'),
            opt.OneOf(
                opt.StrOpt('tenant_id'),
                opt.StrOpt('tenant_name'),
            ),
            opt.Maybe(opt.StrOpt('service_name')),
            opt.Maybe(opt.StrOpt('region')),
        )

    def reauth(self):
        req = {
            'passwordCredentials': {
                'username': self.conf['username'],
                'password': self.conf['password'],
            }
        }
        if 'tenant_id' in self.conf:
            req['tenantId'] = self.conf['tenant_id']
        else:
            req['tenantName'] = self.conf['tenant_name']

        dummy, resp = self.make_json_request({'auth': req})

        try:
            token = resp['access']['token']['id']
            expiry = resp['access']['token'].get('expires')
            if expiry is not None:
                LOGGER.info('Token expires at %s', expiry)
                expiry = time.mktime(time.strptime(
                    expiry.replace('Z', 'UTC'), '%Y-%m-%dT%H:%M:%S%Z'))

            services = [s for s in resp['access']['serviceCatalog']
                        if s.get('type') == 'object-store']
            LOGGER.info('Found services: %r', [s['name'] for s in services])

            if 'service_name' not in self.conf and 'region' not in self.conf:
                LOGGER.info('No service/region specified; '
                            'returning first endpoint.')
                return services[0]['endpoints'][0]['publicURL'], token, expiry

            if 'service_name' in self.conf:
                services = [s for s in services
                            if s['name'] == self.conf['service_name']]

            if len(services) > 1:
                raise base.AuthError(
                    self, 'Multiple services found: %r' % services)

            endpoints = [e for e in services[0]['endpoints']]
            LOGGER.info('Found regions: %r', [e['region'] for e in endpoints])

            if 'region' in self.conf:
                endpoints = [e for e in endpoints
                             if e['region'] == self.conf['region']]

            return endpoints[0]['publicURL'], token, expiry
        except (KeyError, TypeError) as exc:
            raise base.AuthError(self, 'Error in response: %r' % exc)
