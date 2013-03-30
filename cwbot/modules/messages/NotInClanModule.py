from cwbot.modules.BaseKmailModule import BaseKmailModule


class NotInClanModule(BaseKmailModule):
    """ 
    A module that returns a kmail from somebody not in the clan.
    
    No configuration options.
    """
    requiredCapabilities = ['kmail']
    _name = "nonclan"
    
    def __init__(self, manager, identity, config):
        super(NotInClanModule, self).__init__(manager, identity, config)

        
    def _processKmail(self, message):
        if not self.parent.checkClan(message.uid):
            return (self.newMessage(message.uid, "You're not in my clan.")
                    .addItems(message.items))
        return None
