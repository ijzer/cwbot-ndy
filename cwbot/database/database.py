import threading
import csv
import os

__csvDatabases = {}
__dataLock = threading.Lock()


def flush():
    global __csvDatabases
    with __dataLock:
        __csvDatabases = {}


def csvDatabase(dbFileName, folder="cwbot/database/data"):
    global __csvDatabases
    with __dataLock:
        if dbFileName not in __csvDatabases:
            loader = csv.DictReader(open(os.path.join(folder, dbFileName)))
            __csvDatabases[dbFileName] = [record for record in loader
                                          if any(True for v in record.values() 
                                                 if v != "")]
        return __csvDatabases[dbFileName]
    