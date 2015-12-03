'''
Module providing the basics to build an authenticator.
'''
import json
import time

import requests


class AuthError(Exception):
    '''Base class for some type of authentication error.'''
    def __init__(self, source, msg=None):
        super(AuthError, self).__init__(msg)
        self.source = '%s:%s' % (
            source.__class__.__module__,
            source.__class__.__name__)
        self.msg = msg

    def __repr__(self):
        if self.msg is None:
            return '%s(source=%s)' % (
                self.__class__.__name__,
                self.source)
        else:
            return '%s(%s, source=%s)' % (
                self.__class__.__name__,
                self.msg,
                self.source)


class Unauthorized(AuthError):
    '''Client needs to authenticate'''


class Forbidden(AuthError):
    '''Client is not allowed (re-authenticating won't help)'''


class PasswordRequired(AuthError):
    '''A password is required, but was not supplied'''


def error_from_response(response, authenticator):
    '''Given a requests response, instantiate an appropriate AuthError.'''
    if response.status_code == 401:
        return Unauthorized(authenticator)
    if response.status_code == 403:
        return Forbidden(authenticator)
    return AuthError(authenticator, response.status_code)


class BaseAuthenticator(object):
    '''The basic framework of an authenticator.'''
    requires_password = True

    def __init__(self, options, check_insecure=None):
        self.conf = self.__class__.get_opts().validate(options)
        self.storage_url = None
        self.token = ''
        self.expiration_time = None
        self.check_insecure = check_insecure

    def should_verify(self, url):
        return not (self.check_insecure and self.check_insecure(url))

    @property
    def token_has_expired(self):
        if not self.token:
            return True  # No token is never valid
        if self.expiration_time is None:
            return False  # Assume token never expires
        return self.expiration_time < time.time()

    def make_json_request(self, data):
        data = json.dumps(data)
        resp = requests.post(
            self.conf['auth_url'],
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            data=data,
            timeout=10,
            verify=self.should_verify(self.conf['auth_url']))
        if resp.status_code // 100 != 2:
            raise error_from_response(resp, self)

        try:
            resp_data = resp.json()
        except ValueError as exc:
            raise AuthError(self, 'Error parsing response: %r' % exc)
        return resp.headers, resp_data

    @classmethod
    def get_opts(cls):
        '''Get the options for this auth.

        Typically this involves an ``AllOf`` opt.

        :returns: the options for this auth system
        '''
        raise NotImplementedError()

    def get_credentials(self, force_reauth=False):
        '''Get a (potentially cached) set of credentials.

        :returns: a (storage_url, token) pair
        '''
        if self.token_has_expired or force_reauth:
            self.storage_url, self.token, self.expiration_time = self.reauth()
        return self.storage_url, self.token, self.expiration_time

    def reauth(self):
        '''Get a fresh set of credentials.

        :returns: a fresh (storage_url, token, expiration time) triple
        '''
        raise NotImplementedError()
