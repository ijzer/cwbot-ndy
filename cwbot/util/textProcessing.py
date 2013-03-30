def stringToBool(txt):
    """ 
    Converts a string to boolean using the following (case-insensitive) rules:
        true|on|1|yes  -> True
        false|off|0|no -> False
        anything else -> raises KeyError
    """
    try:
        return bool({'true':1,'on':1,'1':1,'yes':1,'false':0,'off':0,'0':0,'no':0}[txt.strip().lower()])
    except KeyError:
        raise ValueError("invalid literal for stringToBool(): '%s'" % txt)


def stringToList(txt):
    """ Convert comma-separated string to list """
    return [item.strip() for item in txt.split(",")]


def listToString(txt):
    return ', '.join(txt) 
    