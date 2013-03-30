class InitData(object):
    """ Class that holds the various classes that need to be passed
    to managers/modules for initialization. """
    def __init__(self, session, chatMan, properties, invMan, dataBase):
        self.session = session
        self.chatManager = chatMan
        self.properties = properties
        self.inventoryManager = invMan
        self.database = dataBase