import logging
import time

import requests

from swiftagent.auth import base
from swiftagent.config import scheme_netloc_only
from swiftagent.models import account
from swiftagent.models import exceptions


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class Cluster(object):
    def __init__(self, authenticator):
        self.auth = authenticator
        storage_url, dummy = self.auth.get_credentials()
        # NB: base_url still includes /v1
        base_url, account_name = storage_url.rstrip('/').rsplit('/', 1)
        self.base_url = base_url
        self.default_account_name = account_name

    def info(self):
        url = scheme_netloc_only(self.base_url) + '/info'

        LOGGER.info('Getting capabilities for %s', url)
        resp = requests.get(url)
        if resp.status_code // 100 != 2:
            raise exceptions.SwiftClientError(resp)

        result = resp.json()
        result.setdefault('timestamp', time.time())
        return result

    @property
    def default_account(self):
        return self.account()

    def account(self, name=None):
        name = name or self.default_account_name
        return account.Account(self, '%s/%s' % (self.base_url, name))

    def authed_req(self, method, url, params=None, headers=None):
        headers = headers or {}
        dummy, token = self.auth.get_credentials()
        if token:
            headers['X-Auth-Token'] = token
        resp = requests.request(
            method, url,
            params=params,
            headers=headers,
            verify=self.auth.should_verify(url))
        if resp.status_code == 401:
            raise base.Unauthorized(self)
        elif resp.status_code == 403:
            raise base.Forbidden(self)
        elif resp.status_code // 100 != 2:
            raise exceptions.SwiftClientError(resp)
        return resp.headers, resp.content
