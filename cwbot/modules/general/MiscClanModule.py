from cwbot.modules.BaseChatModule import BaseChatModule


class MiscClanModule(BaseChatModule):
    """ 
    A module with misc. commands.
    
    No configuration options
    """

    requiredCapabilities = ['chat']
    _name = "misc_clan"
    
    def __init__(self, manager, identity, config):
        super(MiscClanModule, self).__init__(manager, identity, config)


    def _processCommand(self, message, cmd, args):
        if cmd == "donate":
            return ("Want to help the clan and donate hookah parts "
                    "(or anything else)? Send them to me and put 'donate' "
                    "in the message text.")
        return None


    def _availableCommands(self):
        return {'donate': "!donate: How to donate to the clan."}

