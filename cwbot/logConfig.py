import logging, logging.handlers #@UnusedImport

__configDone = False


class ShortLevelNameFormatter(logging.Formatter):
    shortNames = {'DEBUG': 'DBG',
                  'INFO': 'INFO',
                  'WARNING': 'WARN',
                  'ERROR': 'ERR',
                  'CRITICAL': 'CRIT'}
    
    def format(self, record):
        errName = record.levelname
        record.shortlevelname = self.shortNames.get(errName, errName)
        return logging.Formatter.format(self, record)


def logConfig(debug=False):
    """ This function configures the bot's logging capability. """
    global __configDone
    if __configDone:
        return
    __configDone = True
    
    level = logging.DEBUG if debug else logging.INFO
    log = logging.getLogger()
    log.setLevel(level)

    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(level)
    # set a format which is simpler for console use
    cFormatter = ShortLevelNameFormatter(
                "%(asctime)s %(name)-18s: %(shortlevelname)-4s %(message)s",
                "%H:%M")
    # tell the handler to use this format
    console.setFormatter(cFormatter)
    # add the handler to the root logger
    log.addHandler(console)

    fileHandler = logging.handlers.RotatingFileHandler('log/cwbot.log', 
                                                       maxBytes=5000000, 
                                                       backupCount=1, 
                                                       delay=True)
    fFormatter = ShortLevelNameFormatter("%(asctime)s %(name)-20s "
                                         "%(shortlevelname)-4s %(message)s",
                                         '%m-%d %H:%M:%S')
    fileHandler.setFormatter(fFormatter)
    log.addHandler(fileHandler)
    
    
def setFileHandler(logName, fileName):
    """ Set a rotating file handler for the log with name logName. """
    log = logging.getLogger(logName)
    log.handlers = []
    fileHandler = logging.handlers.RotatingFileHandler(fileName, 
                                                       maxBytes=5000000, 
                                                       backupCount=1, 
                                                       delay=True)
    fFormatter = ShortLevelNameFormatter("%(asctime)s %(name)-20s "
                                         "%(shortlevelname)-8s %(message)s",
                                         '%m-%d %H:%M:%S')
    fileHandler.setFormatter(fFormatter)
    log.addHandler(fileHandler)
