'''
Authenticator module for Ye Olde v1 auth.
'''
import logging

from swiftagent.auth import base
from swiftagent import opt


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class V3Authenticator(base.BaseAuthenticator):
    '''Authenticator for auth v3 endpoints.'''
    @classmethod
    def get_opts(cls):
        return opt.AllOf(
            opt.UrlOpt('auth_url'),
            opt.OneOf(
                opt.StrOpt('user_id'),
                opt.AllOf(
                    opt.StrOpt('username'),
                    opt.OneOf(
                        opt.StrOpt('domain_id'),
                        opt.StrOpt('domain_name'),
                    ),
                ),
            ),
            opt.StrOpt('password'),
            opt.Maybe(opt.StrOpt('service_name')),
            opt.Maybe(opt.StrOpt('region')),
            opt.Maybe(opt.StrOpt('interface')),
        )
        # TODO: figure out scope options

    def reauth(self):
        user = {
            'password': self.conf['password']
        }
        if 'user_id' in self.conf:
            user['id'] = self.conf['user_id']
        else:
            user.update({
                'name': self.conf['username'],
                'domain': {}
            })
            if 'domain_id' in self.conf:
                user['domain']['id'] = self.conf['domain_id']
            else:
                user['domain']['name'] = self.conf['domain_name']

        req = {
            'auth': {
                'identity': {
                    'methods': [
                        'password'
                    ],
                    'password': {
                        'user': user
                    }
                }
            }
        }
        # TODO: scope options would be attached immediately under auth

        headers, resp = self.make_json_request(req)

        token = headers['X-Subject-Token']
        try:
            if 'expires_at' in resp['token']:
                LOGGER.info('Token expires at %s',
                            resp['token']['expires_at'])
            services = [s for s in resp['token']['catalog']
                        if s.get('type') == 'object-store']
            LOGGER.info('Found services: %r', [s['name'] for s in services])

            if not any(filter in self.conf for filter in (
                    'service_name', 'region', 'interface')):
                LOGGER.info('No service/region/interface specified; '
                            'returning first endpoint.')
                return services[0]['endpoints'][0]['url'], token

            if 'service_name' in self.conf:
                services = [s for s in services
                            if s['name'] == self.conf['service_name']]

            if len(services) > 1:
                raise base.AuthError(
                    self, 'Multiple services found: %r' % services)

            endpoints = [e for e in services[0]['endpoints']]
            LOGGER.info('Found regions/interfaces: %r', [
                (e['region'], e['interface']) for e in endpoints])

            if 'region' in self.conf:
                endpoints = [e for e in endpoints
                             if e['region'] == self.conf['region']]

            if 'interface' in self.conf:
                endpoints = [e for e in endpoints
                             if e['interface'] == self.conf['interface']]

            return endpoints[0]['url'], token
        except (KeyError, TypeError) as exc:
            raise base.AuthError(self, 'Error in response: %r' % exc)
