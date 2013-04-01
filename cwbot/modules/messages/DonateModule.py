from cwbot.modules.BaseKmailModule import BaseKmailModule


class DonateModule(BaseKmailModule):
    """ 
    A module that handles donation kmails (detects the word "donate" in text)
    
    No configuration options.
    """
    requiredCapabilities = ['kmail']
    _name = "donate"
    
    def __init__(self, manager, identity, config):
        super(DonateModule, self).__init__(manager, identity, config)
        
        
    def _processKmail(self, message):
        if "donate" in message.text.lower():
            if message.meat > 0 or message.items:
                return self.newMessage(message.uid, 
                                       "Thank you for your donation!")
        return None


    def _kmailDescription(self):
        return ("If you want to donate something, include the word "
                "\"donate\" in your kmail.")