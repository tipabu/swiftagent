'''
Low-level tools for interacting with Unix Domain Sockets.
'''
from __future__ import print_function
from __future__ import unicode_literals
import logging
import socket


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def read_line(sock, buf):
    '''Read a single line from a socket.

    :param sock: the socket from which to read
    :param buf:  any already-buffered bytes from the socket
    :returns: a tuple of (utf-8-decoded line, remaining buffer)
    '''
    buf = [buf]
    while b'\n' not in buf[-1]:
        buf.append(sock.recv(16))
        if not buf[-1]:
            break
    line, dummy, buf = b''.join(buf).partition(b'\n')
    return line.decode('utf-8'), buf


class LineOrientedUnixServer(object):
    '''A line-oriented UDS server.

    Connecting clients should send single-line (ie, '\n'-terminated) requests
    and expect single-line responses.

    :param socket_address: the address to which the socket should bind
    :param backlog: the maximum number of queued connections
    '''
    # pylint: disable=too-few-public-methods
    def __init__(self, socket_address, backlog=1):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(socket_address)
        self.sock.listen(backlog)

    def run(self):
        '''Process incoming connections indefinitely.'''
        try:
            while True:
                conn, client_addr = self.sock.accept()
                try:
                    self._handle_connection(conn)
                except socket.timeout:
                    LOGGER.info('Timeout while communicating with %r',
                                client_addr)
                finally:
                    conn.close()
        finally:
            self.sock.close()

    def _handle_connection(self, conn):
        '''Handle a single connection and its potentially numerous requests.

        :param conn: the connection socket
        '''
        conn.settimeout(1)
        buf = b''
        while True:
            data, buf = read_line(conn, buf)
            LOGGER.debug('rx: %r', data)
            if not data:
                break
            resp = self._handle_data(data)
            LOGGER.debug('tx: %r', resp)
            conn.sendall(resp.encode('utf-8'))
            conn.sendall(b'\n')

    def _handle_data(self, data):
        '''Handle data read from the connection.

        This will parse out the first <word> of the line and call a subclass's
        handle_<word>handler.
        '''
        cmd, dummy, data = data.partition(' ')
        handler = getattr(self, 'handle_%s' % cmd, None)
        if not handler:
            return 'ERROR unknown command %s' % cmd
        try:
            return handler(data)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(exc)
            return 'ERROR %r' % exc


class LineOrientedUnixClient(object):
    '''A line-oriented UDS client.

    The client should always send single-line (ie, '\n'-terminated) requests
    to which servers should always respond with single-line responses.

    :param socket_address: the address to which the client should connect
    '''
    def __init__(self, socket_address):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(socket_address)
        self.buf = b''

    def send_command(self, cmd):
        '''Send a single command to the server.

        :param cmd: the command to send
        :returns: the response from the server
        '''
        self.sock.sendall(cmd.encode('utf-8'))
        self.sock.sendall(b'\n')
        data, self.buf = read_line(self.sock, self.buf)
        return data

    def close(self):
        '''Attempt to close the connection to the server gracefully.'''
        self.sock.sendall(b'\n')
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
