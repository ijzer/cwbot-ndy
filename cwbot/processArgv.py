import os
import logging
from cwbot.RunProperties import RunProperties
from cwbot import logConfig

def processArgv(argv):
    """ Process the command line arguments and return a RunProperties object.
    """
    
    log = logging.getLogger()
    cwd = os.getcwd()
    try:
        os.chdir(argv[1])
    except:
        try:
            os.chdir(os.getenv("HOME"))
        except:
            pass
    
    loginFile = 'login.ini'
    adminFile = 'admin.ini'
    
    debug = any(arg for arg in argv if "debug" in arg.lower())
    logConfig.logConfig(debug)
    
    log.info("-------- Startup --------")
    log.info("Using working directory {}".format(os.getcwd()))

    return RunProperties(debug, loginFile, adminFile, cwd)
