from BaseModule import BaseModule


class BaseChatModule(BaseModule):
    """A class to process chat !commands. Adds two extended calls:
    process_command -> _processCommand is called when chat !commands are
    passed through the manager. available_commands -> _avilableCommands
    returns a dict of commands and help text for !help commands and for a 
    few other purposes. """
    requiredCapabilities = []
    _name = ""
    
    
    def __init__(self, manager, identity, config):
        super(BaseChatModule, self).__init__(manager, identity, config)
        self._registerExtendedCall('process_command', self._processCommand)
        self._registerExtendedCall('available_commands', 
                                   self._availableCommands)


    def _processCommand(self, message, commandText, commandArgs):
        """
        Process chat commands (chats which start with !).
        If the module is not set as clan-only, all chats will be sent to this
        function. If it is clan-only, only commands matching those in
        _availableCommands() are sent here.
        
        The derived class should process those that apply and ignore the 
        others. 'message' contains the full message structure as defined by
        pyKol. 'commandText' contains the actual command (without the !) 
        in lower case. 'commandArgs' contains everything else.
        For example "!HeLLo     World 123" -> commandText = "hello", 
                                              commandArgs = "World 123"
        
        This function must return either a string, which will be printed in 
        chat, or None.
        """
        pass
    

    def _availableCommands(self):
        """ Return a dict of available commands. Entries should be in the form
        "command": "text that is shown for help". To keep a command hidden,
        use the format "command": None. """
        return {}
