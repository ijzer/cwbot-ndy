class ModuleEntry(object):
    """ Container object for a module. Managers hold their modules in
    a list of ModuleEntries. """
    def __init__(self, classObj, priority, permission, clanOnly, *args):
        """ Create a new ModuleEntry. The actual object is not created yet;
        here classObj is the class Type object and *args holds the calling
        arguments. The class is only created once createInstance is called. """
        self.module = None
        self.priority = priority
        self.permission = permission
        self.clanOnly = clanOnly
        self._class = classObj
        self._args = args
        self.className = classObj.__name__
        
    def createInstance(self):
        """ Instantiate the module """
        if self.module is not None:
            raise ValueError("Object already initialized!")
        self.module = self._class(*self._args)
   
        
class ManagerEntry(object):
    """ Container object for a Manager. The CommunicationDirect holds its 
    managers in a list of ManagerEntries. """
    def __init__(self, classObj, priority, *args):
        """ Create a new ManagerEntry. The actual object is not created yet;
        here classObj is the class Type object and *args holds the calling
        arguments. The class is only created once createInstance is called. """
        self.manager = None
        self.priority = priority
        self._class = classObj
        self._args = args
        self.className = classObj.__name__

        
    def createInstance(self):
        if self.manager is not None:
            raise ValueError("Object already initialized!")
        self.manager = self._class(*self._args)