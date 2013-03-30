import json
import threading
import datetime
from cwbot.locks import IOLock

def jsonSerialize(filename, obj):
    try:
        with IOLock.lock:
            s = json.dumps(obj, indent=4, sort_keys=True)
            with open(filename, 'w') as fp:
                fp.write(s)
    except:
        print("Exception writing to {}".format(filename))
        raise
            

def jsonDeserialize(filename):
    try:
        with IOLock.lock:
            with open(filename, 'r') as fp:
                return json.load(fp)
    except IOError as e:
        return {'__last_error__': e.args, 
                '__last_err_t__': datetime.datetime.now().strftime('%c')}
    except:
        print("Exception reading {}.".format(filename))
        raise
    
    
def jsonTry(obj):
    try:
        json.dumps([obj])
        return True
    except Exception:
        return False