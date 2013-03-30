import sys
import cwbot.util.DebugThreading as threading

class ExceptionThread(threading.Thread):
    """ A special type of thread that keeps track of exceptions.
    Note that you should override _run() and not run() when you
    derive from ExceptionThread.
    
    If the calling thread calls join(), it will throw whatever
    exception occurred here.
    """
    
    def __init__(self, *args, **kwargs):
        self._exc = None
        self._exc_info = sys.exc_info
        self.exception = threading.Event()
        super(ExceptionThread, self).__init__(*args, **kwargs)
        
    def run(self):
        try:
            self._run()
        except:
            self._exc = self._exc_info()
            self.exception.set()
            
    def _run(self):
        pass
    
    def join(self, timeout=None):
        super(ExceptionThread, self).join(timeout)
        if self._exc is not None:
            e = self._exc
            self._exc = None
            raise e[1], None, e[2]
