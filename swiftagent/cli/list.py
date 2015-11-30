from __future__ import print_function

import argparse
import logging

from swiftagent import config


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true',
                        help='include debugging information')
    args = parser.parse_args(args[1:])

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    conf = config.SwiftConfig()

    for auth, url in conf.available_auths.items():
        print('%-20s %s' % (auth, url or '(no auth)'))
