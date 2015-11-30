'''
Authenticator module that can insteract with a swift-agent server.
'''

from swiftagent.agent import client
from swiftagent.auth import base
from swiftagent import opt


class AgentAuthenticator(base.BaseAuthenticator):
    '''Authenticator that can interact with a swift-agent server.'''
    # agent client will handle password
    password_required = False

    def __init__(self, config_dict):
        super(AgentAuthenticator, self).__init__(config_dict)
        if not client.can_use_swift_agent():
            raise TypeError('AgentAuthenticator requires a running '
                            'swift-agent process')
        self.ever_prompted = False

    @classmethod
    def get_opts(cls):
        return opt.StrOpt('auth_name')

    def reauth(self):
        prompted, (storage_url, token) = client.get_auth_with_unlock(
            self.conf['auth_name'], reauth=True)
        self.ever_prompted = self.ever_prompted or prompted
        return storage_url, token
