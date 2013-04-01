from collections import defaultdict
import weakref

class Kmail(object):
    """ This is a simplified object for holding a Kmail. The PyKol 
    representation of a Kmail is needlessly complicated for most purposes
    here, especially for controlling item additions/removals. 
    Note that a Kmail object cannot be initialized with items in
    it; they must be added manually with .addItem() or .addItems(). """
    
    def __init__(self, uid, text="", meat=0, info=None):
        """ Create a new Kmail object """
        self.uid = uid
        self.text = text
        self.meat = meat
        self.items = defaultdict(lambda: 0)
        self.info = info if info is not None else {}

        
    def __repr__(self):
        return ("uid={}, meat={}, items={}, text='{}'"
                .format(self.uid, self.meat, 
                        dict(self.items.items()), self.text.encode('utf-8')))
    
    
    @classmethod
    def fromPyKol(cls, message):
        """ Create a Kmail object from a PyKol kmail (represented as a dict)
        """
        if message is None:
            return None
        return cls(message['userId'], message.get('text', ""), 
                   message.get('meat', 0), message).addItems( 
                       dict((it['id'], it['quantity']) 
                            for it in message.get('items', [])))
    
    
    def toPyKol(self):
        """ Convert a Kmail object to the PyKol dict format """
        m = self.info
        m.update({'userId': self.uid, 'text': self.text, 'meat': self.meat, 
                  'items': [{'id': id_, 'quantity': qty} 
                            for id_,qty in self.items.items()]})
        return m
    
        
    def addItem(self, itemId, itemQty):
        """ Add a single item to the Kmail """
        self.items[itemId] += itemQty
        return self
    
    
    def addItems(self, itemIdQtyDict):
        """ Add multiple items to the kmail, using a dict of 
        (item-id, quantity) pairs """
        for k,v in itemIdQtyDict.items():
            self.addItem(k,v)
        return self
    
    
class KmailResponse(object):
    """ A container for Kmails sent by a module. The CommunicationDirector
    requires Kmails to be in this container. The message argument should
    be a Kmail object. """
    def __init__(self, manager, module, message):
        self.manager = weakref.proxy(manager)
        self.module = None
        if module is not None:
            self.module = weakref.proxy(module)
        self.kmail = message
        self._info = message.toPyKol()
