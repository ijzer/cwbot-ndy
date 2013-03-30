import os
import logging
import errno
from cwbot.RunProperties import RunProperties
from cwbot import logConfig

def _createDir(name):
    try:
        os.makedirs(name)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    

def processArgv(argv):
    """ Process the command line arguments and return a RunProperties object.
    """
    
    log = logging.getLogger()
    cwd = os.getcwd()
    try:
        os.chdir(argv[1])
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception:
        try:
            os.chdir(os.getenv("HOME"))
        except:
            pass
        
    _createDir("data")
    _createDir("log")
    
    loginFile = 'login.ini'
    adminFile = 'admin.ini'
    
    debug = any(arg for arg in argv if "debug" in arg.lower())
    logConfig.logConfig(debug)
    
    log.info("-------- Startup --------")
    log.info("Using working directory {}".format(os.getcwd()))

    return RunProperties(debug, loginFile, adminFile, cwd)
