'''
Tools for reading and writing data.
'''
from __future__ import print_function
from __future__ import unicode_literals
import collections
from six.moves import shlex_quote


def export(to_export):
    '''Print some key-value pairs as ``export`` lines.

    If the value is falsey, print an ``unset`` line instead.

    :param to_export: the dict or list of tuples to export
    '''
    if isinstance(to_export, collections.Mapping):
        to_export = sorted(to_export.items())
    for key, value in sorted(to_export):
        if value:
            print('export %s=%s' % (key, shlex_quote(str(value))))
        else:
            print('unset %s' % key)
