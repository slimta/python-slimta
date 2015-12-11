def check_argtype(val, type_, name, or_none=False):
    """ Checks the type of an argument

    :param type_: type or list of types
    :raise: TypeError
    """
    if not (isinstance(val, type_) or (or_none and val is None)):
        raise TypeError('{} should be of type {}, got {}'.format(
            name, type_, type(val)))
