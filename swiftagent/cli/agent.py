from __future__ import print_function
from __future__ import unicode_literals
import argparse
import logging
import os
import signal
import stat
import subprocess
import sys
import tempfile

from swiftagent.agent import client
from swiftagent.agent import server
from swiftagent import io


def tolerate(os_err_tuple, func, *args):
    '''Call a function, ignoring a specific type of OSError.

    :param os_err_tuple: a tuple (usually like ``(errno, description)``)
                         describing the error to tolerate
    :param func: the function to call
    :param args: the arguments which which to call the function
    '''
    try:
        func(*args)
    except OSError as exc:
        if exc.args != os_err_tuple:
            raise


def cleanup():
    '''Clean up any existing Swift Agents.

    This inspects the environment to determine:
      * whether a swift-agent process is already running; if so, attempt to
        gracefully shut it down via an interrupt signal, similar to a Ctrl-C,
        and
      * whether a swift-agent socket has been created; if so, attempt to
        delete it and clean up the temporary directory for it.
    '''
    pid = os.environ.get(client.PROCESS_ID_ENV_VAR)
    if pid:
        tolerate((3, 'No such process'),
                 os.kill, int(pid), signal.SIGINT)

    socket_addr = os.environ.get(client.SOCKET_ENV_VAR)
    if socket_addr:
        tolerate((2, 'No such file or directory'),
                 os.unlink, socket_addr)
        tolerate((2, 'No such file or directory'),
                 os.rmdir, os.path.dirname(socket_addr))


def main(args):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--daemon', dest='socket_addr')
    group.add_argument('--stop', action='store_true')
    group.add_argument('--debug', action='store_true')
    args = parser.parse_args(args[1:])

    if args.socket_addr:
        logging.basicConfig(level=logging.DEBUG)
        server.SwiftAgentServer(args.socket_addr).run()
        return

    cleanup()
    if args.stop:
        io.export({client.SOCKET_ENV_VAR: None,
                   client.PROCESS_ID_ENV_VAR: None})
        return

    if args.debug:
        agent_out = os.open(os.path.expanduser('~/.swift-agent.log'),
                            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                            stat.S_IRUSR | stat.S_IWUSR)
    else:
        agent_out = open('/dev/null', 'w')

    socket_addr = os.path.join(tempfile.mkdtemp(), 'socket')
    pid = subprocess.Popen([sys.argv[0], '--daemon', socket_addr],
                           preexec_fn=os.setpgrp,
                           stdout=agent_out, stderr=agent_out,
                           stdin=open('/dev/null', 'r')).pid
    io.export({client.SOCKET_ENV_VAR: socket_addr,
               client.PROCESS_ID_ENV_VAR: pid})
