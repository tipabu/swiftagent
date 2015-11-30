from six.moves import urllib
# Yeah, yeah... these are all pretty bare right now.
# pylint: disable=too-few-public-methods


class Opt(object):
    '''Basic option interface.'''
    def validate(self, input_dict):
        '''Validate some input.

        :param input_dict: the complete input dictionary
        :returns: a dictionary of parsed inputs
        '''
        raise NotImplementedError()


# ==============
# Simple options
# ==============


class StrOpt(Opt):
    '''A generic string option.

    :param name:      the name of the option
    :param default:   the default for the option,
                      or None if the option is required
    :param help_text: a description of the option
    '''
    def __init__(self, name, default=None, help_text=None):
        self.name = name
        self.default = default
        self.help_text = help_text

    def validate(self, input_dict):
        value = input_dict.get(self.name, self.default)
        if value is None:
            raise ValueError('Option %s is required' % self.name)
        return {self.name: str(value)}


class IntOpt(StrOpt):
    '''An option that must be an integer.'''
    def validate(self, input_dict):
        output_dict = super(IntOpt, self).validate(input_dict)
        try:
            output_dict[self.name] = int(output_dict[self.name], base=10)
        except ValueError:
            raise ValueError('Option %s must be a valid integer' % self.name)
        return output_dict


class UrlOpt(StrOpt):
    '''An option that must be an absolute URL.'''
    def validate(self, input_dict):
        output_dict = super(UrlOpt, self).validate(input_dict)
        url_parts = urllib.parse.urlparse(output_dict[self.name])
        if not (url_parts.scheme and url_parts.netloc):
            raise ValueError('Option %s must be a valid URL' % self.name)
        return output_dict


# ========================
# More complicated options
# ========================


class Maybe(Opt):
    '''Wrap an option so it's no longer required.'''
    def __init__(self, wrapped_opt):
        self.opt = wrapped_opt
        self.name = '%s?' % wrapped_opt.name

    def validate(self, input_dict):
        try:
            return self.opt.validate(input_dict)
        except ValueError:
            # Eh, we tried.
            return {}


class AllOf(Opt):
    '''Group several options together; they will all be required.'''
    def __init__(self, *wrapped_opts):
        self.opts = wrapped_opts
        self.name = ', '.join([o.name for o in wrapped_opts])

    def validate(self, input_dict):
        output_dict = {}
        for opt in self.opts:
            output_dict.update(opt.validate(input_dict))
        return output_dict


class OneOf(Opt):
    '''Group several options together; the first valid option is returned.'''
    def __init__(self, *wrapped_opts):
        self.opts = wrapped_opts
        self.name = '[ %s ]' % ' | '.join([o.name for o in wrapped_opts])

    def validate(self, input_dict):
        for opt in self.opts:
            try:
                return opt.validate(input_dict)
            except ValueError:
                pass
        raise ValueError('One of %r is required' % [o.name for o in self.opts])
