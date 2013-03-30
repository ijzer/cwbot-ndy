import re
from BaseManager import BaseManager
from cwbot.util.textProcessing import stringToBool

class BaseChatManager(BaseManager):
    """
    Base class for any Manager that handles chats. The parseChat() method
    is overridden to handle any chat that is approved in the _chatApplies()
    method.
    """ 
    
    capabilities = ['chat', 'inventory', 'admin']

    def _chatApplies(self, x, checkNum):
        """ Returns True if the manager should process this chat. This
        function should be overridden in derived classes to impliment
        different behavior. By default, the manager processes every public
        chat, and also accepts PMs if its accept_private_messages option
        is set in modules.ini. """
        return (x['type'] in ['normal', 'listen', 'emote'] or 
                (self._respondToWhisper and x['type'] == 'private'))
        
    
    def __init__(self, parent, name, iData, config):
        "Initialize the BaseChatManager"
        self._respondToWhisper = None
        super(BaseChatManager, self).__init__(parent, name, iData, config)
        
        
    def _configure(self, config):
        """Configuration. In addition to the BaseManager config, the
        accept_private_messages option is added for the BaseChatManager. """
        super(BaseChatManager, self)._configure(config)
        try:
            self._respondToWhisper = stringToBool(
                    config.setdefault('accept_private_messages', 'true'))
        except KeyError:
            raise Exception("Invalid option to accept_private_messages "
                            "for manager {}".format(self.identity))
    
    
    def _processChat(self, msg, checkNum):
        """ Every approved chat is passed to the _processChat method. Here
        the chat is passed to individual modules. """
        replies = []
        txt = msg['text']
        # check if this is a command or help query (starts with ? or !) that
        # is of the form "!COMMAND (ARGS)"
        m1 = re.search(r'^(!|\?)([^\s(]+)\s*\((.*)\)', txt)
        cmdtype = []
        cmd = []
        arg = []
        if m1 is not None:
            cmdtype = m1.group(1)
            cmd = m1.group(2).lower()
            arg = m1.group(3)
        else:
            # check for the form "!COMMAND ARGS", discard -hic- if present
            m2 = re.search(r'^(!|\?)([^\s(]+)\s*(.*?)(\s*-hic-)?$', txt)
            if m2 is not None:
                cmdtype = m2.group(1)
                cmd = m2.group(2).lower()
                arg = m2.group(3)
            else:
                cmdtype = None
                cmd = None
                arg = None
        if arg is None:
            arg = "" 
        if cmd == "help" or cmdtype == "?":
            # show "help" text
            replies.extend(self._showHelp(msg, cmd, arg))
        else:
            # execute command
            with self._syncLock:    
                for m in self._modules:
                    mod = m.module
                    permission = m.permission
                    clanOnly = m.clanOnly
                    # ACTUALLY execute the command
                    txt = self._processCommand(mod, permission, clanOnly, msg, 
                                              cmd, arg)
                    if txt is not None:
                        replies.extend(txt.split("\n"))
        return replies

    
    def _processCommand(self, module, permission, clanOnly, msg, cmd, arg):
        """ This function is used to send a chat to a module, while first
        checking permissions and in-clan status. """
        
        # get a list of available chat commands
        uid = msg['userId']
        availableCommands = module.extendedCall('available_commands')
        if availableCommands is None:
            availableCommands = {}
        noPermission = (permission is None or 
                        permission == "" or 
                        permission == "None")
        cmdAvailable = (cmd in availableCommands)
        
        # first, perform in-clan check
        if clanOnly:
            if cmdAvailable:
                # command is verified as a command of the selected module.
                # proceed with clan verification
                if not self.checkClan(uid):
                    return None
            else:
                # command is not in the selected module's commands. Skip
                # verification and assume that the user is not in-clan to
                # improve responsiveness.
                return None
        
        # now, check permissions
        if noPermission:
            # send all chats (even non-commands) to this module because
            # it has no restrictions
            return module.extendedCall('process_command', msg, cmd, arg)
        elif permission in self.properties.getPermissions(uid):
            # the user has permission to execute the command
            if cmdAvailable:
                self._log.info("Administrator {} ({}) has used permission "
                               "{} to execute command '!{}({})'."
                               .format(msg['userId'], 
                                       msg.get('userName', ""), 
                                       permission, cmd, arg))
            return module.extendedCall('process_command', msg, cmd, arg)
        else:
            # user does not have required permissions
            if cmdAvailable:
                self._log.info("User {} ({}) does not have required "
                               "permission {} to execute command '!{}({})'."
                               .format(uid, msg.get('userName', ""), 
                                       permission, cmd, arg))
                return "You do not have permission to use that command."
            else:
                return None

    
    def _showHelp(self, msg, cmd, arg):
        """ Return the help text that shows available commands. This is
        done using the available_commands extended module call, which is
        set up for all classes deriving from BaseChatModule. """
        helpText = []
        availableCommands = dict()
        availableAdmin = dict()
        uid = msg['userId']
        availablePermissions = self.properties.getPermissions(uid)

        # "help" accepts two forms: "?COMMAND" and "!help COMMAND". Here
        # the latter is transformed to the former.
        if cmd == "help" and arg != "":
            cmd = arg
        cmd = cmd.lower()
        generalHelp = (cmd == "help")
        
        # get a list of all matching commands
        for m in self._modules:
            mod = m.module
            permission = m.permission
            clanOnly = m.clanOnly
            newCmds = mod.extendedCall('available_commands')
            if newCmds is not None:
                # remove commands with no description (alternates / hidden)
                newCmds = dict((k.lower(),v) for k,v in newCmds.items() 
                               if v is not None)
                if generalHelp or cmd in newCmds:
                    if not clanOnly or self.checkClan(uid):
                        if (permission is None or permission == "" or 
                            permission == "None"):
                            availableCommands.update(newCmds)
                        elif permission in availablePermissions:
                            availableAdmin.update(newCmds)
                    
        if generalHelp:
            helpText.extend(self._showCommandSummary(
                                  msg, availableCommands, availableAdmin))
        else:
            if cmd in availableCommands:
                helpText.append(availableCommands[cmd])
            elif cmd in availableAdmin:
                helpText.append("[Admin] " + availableAdmin[cmd])
        return helpText
        

    def _showCommandSummary(self, msg, availableCommands, availableAdmin):
        """ Generate the text for a general help inquiry """
        txt = []
        if availableCommands is not None and len(availableCommands) > 0:
            txt.append("Available commands: !{}."
                       .format(', !'.join(item for item in availableCommands)))
        if availableAdmin is not None and len(availableAdmin) > 0:
            txt.append("Admin commands available to {}: !{}"
                       .format(msg.get('userName', msg['userId']), 
                               ', !'.join(item for item in availableAdmin)))
        return txt
    
        
    def parseChat(self, msg, checkNum):
        """
        This function is called by the CommunicationDirector FOR EACH CHAT 
        RECEIVED after it checks for new chats. New chats received at the same
        time will have equal checkNum values.
        """
        if self._chatApplies(msg, checkNum):
            return self._processChat(msg, checkNum)
        return []
