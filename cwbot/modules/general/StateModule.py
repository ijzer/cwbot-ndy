from cwbot.modules.BaseChatModule import BaseChatModule


class StateModule(BaseChatModule):
    """ 
    A module that displays the state of other modules (provided they
    respond to a "state" event subject). This is for debugging, so
    it should be behind a permission setting.
    
    No configuration options.
    """
    requiredCapabilities = ['chat']
    _name = "state"
    
    def __init__(self, manager, identity, config):
        super(StateModule, self).__init__(manager, identity, config)


    def _processCommand(self, msg, cmd, args):
        if cmd == "state": 
            if args is not None and len(args)>0:
                replies = self._raiseEvent("state", args)
                if len(replies) > 0:
                    return "\n".join(("{} {}".format(r.fromIdentity, 
                                                     r.data)
                                      for r in replies if r is not None))
                return "Module {} does not exist or has no state.".format(args)
            replies = self._raiseEvent("state")
            return "\n".join(("{} {}".format(r.fromIdentity, r.data)
                              for r in replies if r is not None))
        return None


    def _availableCommands(self):
        return {'state': "!state: display module state information."}

