import cwbot.util.DebugThreading as threading

class InventoryLock(object):
    lock = threading.RLock()
    
class KmailLock(object):
    lock = threading.RLock()
