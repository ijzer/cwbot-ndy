import signal, errno
from contextlib import contextmanager
import fcntl

import sys
from cwbot.main import main

@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        pass

    original_handler = signal.signal(signal.SIGALRM, timeout_handler)

    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

with timeout(1):
    f = open("ndy.lck", "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except IOError, e:
        if e.errno != errno.EINTR:
            raise e
        print "Lock timed out"
        sys.exit(3)

main()