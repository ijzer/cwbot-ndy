import threading
import time as _time
import uuid as _uuid
import collections as _collections
from threading import (active_count, activeCount, Condition,     #@UnusedImport
                       current_thread, currentThread, enumerate, #@UnusedImport
                       Event, local, Thread, Timer, settrace,    #@UnusedImport
                       setprofile, stack_size, ThreadError)      #@UnusedImport
from cwbot.util import stacktracer as _stacktracer

# usage: import DebugThreading as threading
#
# special debug-threading module. If a deadlock is detected,
# a trace.html file will be generated with a list of thread stack traces.
#
# the cost of using the debug locks/semaphores is:
# a separate debug thread begins running as soon as the first debug
# resource is created. In addition, during acquisition, the debug 
# resources place an ID code in a collections.deque, and suffer any
# penalties for that (might be a global lock).

_waitTime = 30


def _start_trace():
    try:
        _stacktracer.trace_start("trace.html",interval=5,auto=True)
        print("Possible deadlock detected. See trace.html.")
    except Exception:
        pass
        
        
def _stop_trace():
    try:
        _stacktracer.trace_stop()
        print("Deadlock resolved, trace stopped.")
    except Exception:
        pass
    
    
def _reset_traceback():
    try:
        _stacktracer.trace_stop()
    except Exception:
        pass
        

class _DebugThread(threading.Thread):
    """ Thread that tracks lock acquisitions. """
    def __init__(self):
        self._waiting = {} # maps ID code -> time of waiting
        self._queue = _collections.deque() # queue of new ID codes
        self._deadlocked = False
        super(_DebugThread, self).__init__(name="DebugThreading-Thread")
        
    def setWaiting(self, idCode):
        self._queue.append(idCode)
    
    def setDone(self, idCode):
        # ID codes are used exactly twice -- once when requesting resource,
        # and once after the resource is granted. So the ID codes can
        # act as a toggle.
        self._queue.append(idCode)
            
    def run(self):
        while True:
            _time.sleep(5)
            
            # read new ID codes
            while self._queue:
                idCode = self._queue.pop()
                self._toggle(idCode)
                
            if self._waiting:
                now = _time.time()
                maxWait = max((now - then) for then in self._waiting.values())
                if maxWait < _waitTime and self._deadlocked:
                    # deadlock resolved
                    self._deadlocked = False
                    _stop_trace()
                elif maxWait >= _waitTime and not self._deadlocked:
                    # deadlock encountered
                    self._deadlocked = True
                    _start_trace()
                    
    def _toggle(self, idCode):
        if idCode in self._waiting:
            self._waiting.pop(idCode)
        else:
            self._waiting[idCode] = _time.time()


class _DebugWrapper(object):
    """ Class that wraps acquire() and release() behavior to track
    requests by generating an ID and informing the _DebugThread when
    it requests and then acquires an object.
    """
    
    _onceFlag = threading.Event()
    _onceLock = threading.Lock()
    _debugThread = None
    
    def __init__(self, obj):
        self._initDebugThread()
        self._obj = obj
        
    def _initDebugThread(self):
        if self._onceFlag.is_set():
            return
        with self._onceLock:
            if self._onceFlag.is_set():
                return
            # exactly one thread will get here
            _DebugWrapper._debugThread = _DebugThread()
            _DebugWrapper._debugThread.daemon = True
            _DebugWrapper._debugThread.start()
            self._onceFlag.set()
    
    def acquire(self, *args, **kwargs):
        # do not acquire any locks until the debug thread is running
        self._onceFlag.wait() 
        idCode = self._id = _uuid.uuid4().hex # generate unique ID code
        self._debugThread.setWaiting(idCode) # give ID code to thread
        try:
            # actually acquire the object
            return self._obj.acquire(*args, **kwargs)
        finally:
            # give ID code to thread again, so it knows we are done
            self._debugThread.setDone(idCode) 
            
    def release(self, *args, **kwargs):
        return self._obj.release(*args, **kwargs)
    
    __enter__ = acquire
    
    def __exit__(self, t, v, tb):
        self.release()
        
    def __repr__(self):
        return self._obj.__repr__()
    

def Lock(*args, **kwargs):
    return _DebugWrapper(threading.Lock(*args, **kwargs))

def RLock(*args, **kwargs):
    return _DebugWrapper(threading.RLock(*args, **kwargs))

def Semaphore(*args, **kwargs):
    return _DebugWrapper(threading.Semaphore(*args, **kwargs))

def BoundedSemaphore(*args, **kwargs):
    return _DebugWrapper(threading.BoundedSemaphore(*args, **kwargs))
    
    
    
# for testing purposes
def __deadlockThread(evt1, evt2, lock1, lock2):
    with lock1:
        evt1.set()
        evt2.wait()
        with lock2:
            pass
    
    
def __DeadlockTest_Do_Not_Use():
    print("Performing deadlock test.")
    e1 = Event(); e2 = Event(); e3 = Event()
    l1 = Lock(); l2 = Lock()
    # thread1 will acquire lock1 and try to get lock2 when e3 is set
    t1 = Thread(target=__deadlockThread, args=(e1,e3,l1,l2))
    # read1 will acquire lock2 and try to get lock1 when e3 is set    
    t2 = Thread(target=__deadlockThread, args=(e2,e3,l2,l1))
    t1.daemon = True; t2.daemon = True
    t1.start(); t2.start()
    e1.wait(); e2.wait()
    e3.set()
    # threads will never join
    t1.join(); t2.join()
    
if __name__ == "__main__":
    print("Testing deadlocking. Please wait {} seconds.".format(_waitTime))
    __DeadlockTest_Do_Not_Use()
    