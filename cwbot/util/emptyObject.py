class EmptyObject(object):
    def __init__(self, *args, **kwargs):
        if args:
            raise Exception("EmptyObject initialized with args: {!s}"
                            .format(args))
        if kwargs:
            raise Exception("EmptyObject initialized with kwargs: {!s}"
                            .format(kwargs))