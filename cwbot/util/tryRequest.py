import time
import cwbot.util.DebugThreading as threading
import kol.Error
import urllib2, urllib

def emptyFunction():
    pass


def tryRequest(requestObj, nothrow=False, numTries=3, initialDelay=1, 
               scaleFactor=2):
    """Try to execute a request a number of times before throwing, or 
    optionally swallowing the error and returning None."""
    for i in range(numTries):
        try:
            result = requestObj.doRequest()
            return result
        except (kol.Error.Error, 
                urllib2.URLError, 
                urllib.ContentTooShortError):
            if i != numTries - 1:
                time.sleep(initialDelay * scaleFactor ** i)
            elif not nothrow:
                raise
    return None
    
    
class ThreadedRequest(threading.Thread):
    def __init__(self, request, callFunc, numTries, initialDelay, scaleFactor):
        self._request = request
        self._callFunc = callFunc
        self._numTries = numTries
        self._initialDelay = initialDelay
        self._scaleFactor = scaleFactor
        super(ThreadedRequest, self).__init__()
        
    def run(self):
        result = tryRequest(self._request, True, self._numTries, 
                            self._initialDelay, self._scaleFactor)
        self._callFunc(result)


def tryRequestThreaded(requestObj, callFunc=emptyFunction, numTries=3, 
                       initialDelay=1, scaleFactor=2):
    """Try to execute a request in a new thread, and call callFunc with 
    the results (None if an exception occurred)"""
    t = ThreadedRequest(requestObj, callFunc, numTries, 
                        initialDelay, scaleFactor)
    t.start()
    
