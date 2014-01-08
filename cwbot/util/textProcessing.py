
def stringToBool(txt):
    """ 
    Converts a string to boolean using the following (case-insensitive) rules:
        true|on|1|yes  -> True
        false|off|0|no -> False
        anything else -> raises KeyError
    """
    try:
        return bool({'true':1,'on':1,'1':1,'yes':1,
                     'false':0,'off':0,'0':0,'no':0}
                    [txt.strip().lower()])
    except KeyError:
        raise ValueError("invalid literal for stringToBool(): '%s'" % txt)


def stringToList(txt):
    """ Convert comma-separated string to list """
    txt1 = toTypeOrNone(txt)
    if txt1 is None:
        return []
    list_ = [item.strip() for item in txt.split(",")]
    listWithNones = map(toTypeOrNone, list_)
    if any(True for x in listWithNones if x is not None):
        return list_
    return []


def listToString(txt):
    return ', '.join(txt) 
    
    
def toTypeOrNone(val, type_=str):
    if val is None:
        return None
    if str(val).lower() in ["''", '""', "none", ""]:
        return None
    return type_(val)


def intOrFloatToString(val, numDecimal=2):
    if int(val) == float(val):
        return str(int(val))
    return "{0:.{1}f}".format(val, numDecimal)
