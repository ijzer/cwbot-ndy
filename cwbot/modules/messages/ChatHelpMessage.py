from cwbot.modules.BaseKmailModule import BaseKmailModule


class ChatHelpMessage(BaseKmailModule):
    """ 
    This module doesn't do anything. It just shows a message about how to get
    help in chat.
    """
    requiredCapabilities = []
    _name = "chat_help_msg"
    
    def _kmailDescription(self):
        return ("If you want a list of chat commands, send me a PM with the "
                "text '!help' for all available commands. You can also use "
                "!help COMMAND_NAME to get detailed information on a "
                "specific command.")