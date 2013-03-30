from cwbot.modules.BaseChatModule import BaseChatModule


class PermissionsModule(BaseChatModule):
    """ 
    A module that displays your permissions.
    
    No configuration options.
    """
    requiredCapabilities = ['chat']
    _name = "permissions"
    
    def __init__(self, manager, identity, config):
        super(PermissionsModule, self).__init__(manager, identity, config)


    def _processCommand(self, message, cmd, args):
        if cmd == "permissions":
            perms = self.properties.getPermissions(message['userId'])
            if len(perms) == 0:
                return ("User {} has no administrative privileges."
                        .format(message.get('userName', "")))
            else:
                return ("User {} has the following administrative "
                        "privileges: {}".format(message.get('userName', ""), 
                                                ', '.join(perms)))
        return None


    def availableCommands(self):
        return {'permissions': "!permissions: show your permissions list."}

