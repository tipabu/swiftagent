class Account(object):
    def __init__(self, cluster, url, headers=None):
        self.cluster = cluster
        self.url = url
        self.headers = headers or {}

    def info(self, force_refresh=False):
        if not self.headers or force_refresh:
            self.headers, dummy = self.cluster.authed_req('HEAD', self.url)
        return self.headers
