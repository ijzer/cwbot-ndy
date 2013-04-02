import os
import logging
import errno
import argparse
from cwbot.RunProperties import RunProperties
from cwbot import logConfig


def _parse():
    p = argparse.ArgumentParser(
                        add_help=False, 
                        formatter_class=argparse.RawDescriptionHelpFormatter,
                        epilog=' ')
    p.add_argument('--help', '-h', '-?', action='help', 
                   help="show this message", )
    p.add_argument('--debug', action='store_true', help="Run in debug mode")
    p.add_argument('--login', nargs=2, help="use an alternate account",
                   metavar=('USER', 'PASS'))
    p.add_argument('path', default=None, nargs='?',
                   help="run path (default: same path as cwbot.py)")
    p.add_argument('-v', '--version', action='version', 
                   version=RunProperties.version)
    return p.parse_args()


def _createDir(name):
    try:
        os.makedirs(name)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            if exception.errno == errno.EACCES:
                if not os.path.exists(name):
                    raise
            raise
    

def processArgv(argv, curFolder):
    """ Process the command line arguments and return a RunProperties object.
    """
    
    log = logging.getLogger()
    parsed = _parse()
    if parsed.path:
        curFolder = parsed.path
    cwd = os.getcwd()
    os.chdir(curFolder)
        
    _createDir("data")
    _createDir("log")
    
    loginFile = 'login.ini'
    adminFile = 'admin.ini'
    altLogin = parsed.login
    debug = parsed.debug
    
    logConfig.logConfig(debug)
    
    log.info("-------- Startup --------")
    log.info("Using working directory {}".format(os.getcwd()))

    return RunProperties(debug, loginFile, adminFile, cwd, altLogin=altLogin)
