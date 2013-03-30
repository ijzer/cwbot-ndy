import weakref
import logging
import cwbot.util.DebugThreading as threading
from cwbot.util.emptyObject import EmptyObject


class EventData(object):
    def __init__(self, fromType, fromIdentity, to, subject, data={}, **kwargs):
        self.fromName = fromType
        self.fromIdentity = fromIdentity
        self.to = to
        self.subject = subject
        self.data = data
    
    def __repr__(self):
        return ("<{0.fromIdentity} ({0.fromName}) "
                "-> {0.to}: {0.subject} ({0.data})>"
                .format(self))

class EventSubsystem(object):
    """ The class that handles the event subsystem.
    
    To use the event subsystem in your class, derive from 
    EventSubsystem.EventCapable. See full documentation in that class.
    """
    
    _lock = threading.RLock()
    class EventException(Exception):
        pass
    
    
    class DuplicateObjectException(Exception):
        pass

    
    class __EventObject(object):
        def __init__(self, obj, typeString, identityString, callback):
            self.obj = weakref.ref(obj)
            self.type = typeString.lower().strip()
            self.id = identityString.lower().strip()
            self.callback = callback

    
    class EventCapable(EmptyObject):
        """An event-capable class has two "names": a name, which 
        describes its class, and an identity, which is a string unique to each
        instance. Event-capable classes can be registered to one 
        EventSubsystem instance at maximum. Registration can either be done 
        automatically in __init__() or using the eventRegister() method. The 
        eventUnregister() method removes the instance from its EventSubsystem. 
        
        To raise an event, use the _raiseEvent() method. Each event has a 
        subject, which should be a string. A receiver can be specified, 
        meaning only a matching object will be notified of the event. To match
        by type name, simply specify the type name as the receiver. To match 
        by identity, use __identity__, where identity is the identity name of 
        the object (for example, "__system__"). If the receiver is None, the 
        event will be broadcast to all objects registered to the 
        EventSubsystem. Events also have a data attribute, which is a dict
        that may hold additional information.
            
        When an event is raised and received by an event-capable class, the
        _eventCallback() method is called, with an EventData struct as the 
        argument. The programmer should check the subject of the event to see 
        if it should be processed. Optionally, the object can send a reply back
        to the object that raised the event using the _eventReply() method. 
        This does not trigger an event; instead, the EventSubsystem collects 
        all replies into a list, which is returned when _raiseEvent() has 
        completed. Each _eventReply() call will create an EventData object in
        the returned list. _eventReply() should ONLY be called inside
        the _eventCallback() function.
        
        It is possible to raise an event inside another event. Events are 
        tracked in a stack. Event behavior is single-threaded.
        
        Be careful raising events inside threads. The Event Subsystem uses
        internal locking, so be careful not to cause any deadlocks.
        """

        def __init__(self, name, identity, evSys=None, **kwargs):
            self.__lock = threading.RLock()
            self.__type = name
            self.__id = "__" + identity.lower().strip() + "__"
            self.__ev = None
            self.__registered = threading.Lock()
            if evSys is not None:
                self.eventRegister(evSys)
            super(EventSubsystem.EventCapable, self).__init__(**kwargs)
                
        
        def __del__(self):
            if self.__ev is not None:
                self.eventUnregister()
                
                
        def __eventCallback(self, eData):
            self._eventCallback(eData)

        
        @property
        def eventSubsystem(self):
            return self.__ev
                
            
        def eventRegister(self, evSubsystem):
            if not self.__registered.acquire(False):
                raise EventSubsystem.EventException(
                        "Object {} ({}) is already assigned"
                        " to an event subsystem."
                        .format(self.__id, self.__type))
            with self.__lock:
                evSubsystem.registerObject(
                        self, self.__type, self.__id, self.__eventCallback)
                self.__ev = evSubsystem
            
            
        def eventUnregister(self):
            with self.__lock:
                if self.__ev is not None:
                    self.__ev.unregisterObject(self)
                    self.__ev = None
                    try:
                        self.__registered.release()
                    except threading.ThreadError:
                        pass
            
            
        def _raiseEvent(self, subject, receiver=None, data={}, **kwargs):
            if self.__ev is None:
                raise EventSubsystem.EventException(
                    "Object {} ({}) has no event subsystem."
                    .format(self.__id, self.__type))
            return self.__ev.raiseEvent(
                    self.__type, self.__id, receiver, subject, data)
        
        
        def _eventReply(self, data={}, **kwargs):
            if self.__ev is None:
                raise EventSubsystem.EventException(
                        "Object {} ({}) has no event subsystem."
                        .format(self.__id, self.__type))
            self.__ev.eventReply(self.__type, self.__id, data)
            
            
        def _eventCallback(self, eData):
            pass
        
        
    def __init__(self):
        self._eventObjects = []
        self._replyStack = []
        self._eventStack = []
        self._log = logging.getLogger("events")
        
        
    def _clearDead(self):
        with self._lock:
            self._eventObjects = [eo for eo in self._eventObjects 
                                  if eo.obj() is not None]
        
    
    def registerObject(self, obj, typeString, identityString, callback):
        with self._lock:
            newEO = self.__EventObject(
                    obj, typeString, identityString, callback)
            if any(True for eo in self._eventObjects if eo.id == newEO.id):
                raise EventSubsystem.DuplicateObjectException(
                        "An object with identity {} is already registered."
                        .format(newEO.id))
            if any(True for eo in self._eventObjects if eo.obj() is obj):
                raise EventSubsystem.DuplicateObjectException(
                        "Duplicate object {} ({}) registered."
                        .format(newEO.id, newEO.type))
            self._eventObjects.append(newEO)
#            print("Registered object {!s} with event subsystem."
#                  .format(obj))

        
    def unregisterObject(self, obj):
        with self._lock:
            self._clearDead()
            if obj is not None:
                oldSize = len(self._eventObjects)
                self._eventObjects = [
                        eo for eo in self._eventObjects 
                        if eo.obj() is not obj
                        and obj is not None]
                sizeDiff = oldSize - len(self._eventObjects)
                if sizeDiff == 0:
                    raise ValueError("Object {!s} is not registered."
                                     .format(obj))
                elif sizeDiff > 1:
                    raise Exception(
                          "Internal error: duplicate objects {!s} "
                          "detected in event registry.".format(obj))


    def raiseEvent(self, senderType, senderId, receiver, 
                   subject, data):
        with self._lock:
            if subject is None:
                raise self.EventException("Null event not allowed.")
            e = EventData(senderType, senderId, receiver, subject, data)
            eventDepth = len(self._eventStack)
            self._log.debug("{}Event raised: {}"
                            .format("  " * eventDepth,e))
            self._clearDead()
            self._eventStack.append(senderId)
            self._replyStack.append([])
            if receiver is not None:
                receiver = receiver.lower().strip()
            for eventObj in self._eventObjects:
                if (receiver is None or 
                        receiver == eventObj.type or receiver == eventObj.id):
                    o = eventObj.obj()
                    if o is not None:
                        # may modify self._replies
                        eventObj.callback(e)
            replies = self._replyStack.pop()
            self._eventStack.pop()
            return replies
        
    
    def eventReply(self, rType, rId, data):
        with self._lock:
            if not self._eventStack:
                raise EventSubsystem.EventException(
                        "Can't reply outside of event")
            eventDepth = len(self._eventStack)
            self._log.debug("{}Received reply: {} ({}): {}"
                            .format("  " * eventDepth, rId, rType, data))
            self._replyStack[-1].append(EventData(
                        rType, rId, self._eventStack[-1], "reply", data))
