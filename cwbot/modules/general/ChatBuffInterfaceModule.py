from cwbot.modules.BaseChatModule import BaseChatModule
from cwbot.util.textProcessing import toTypeOrNone

class ChatBuffInterfaceModule(BaseChatModule):
    _name = "ChatBuffInterface"
    requiredCapabilities = ['chat', 'inventory']
    
    def __init__(self, manager, identity, config):
        self._buffs = None
        self._buffer = None
        super(ChatBuffInterfaceModule, self).__init__(manager, identity, 
                                                      config)
        
    def _configure(self, config):
        self._buffer = toTypeOrNone(config.setdefault('buff_module', 'none'))
        buffList = config.setdefault('buffs', {})
        self._buffs = dict((k.strip().lower(), v.strip())
                           for k,v in buffList.items())
        
    
    def _processCommand(self, msg, cmd, args):
        if cmd == "buff":
            if args.strip() == "":
                buffList = []
                for k,v in self._buffs.items():
                    result = self._raiseEvent('buff_info', self._buffer,
                                              {'userId': msg['userId'],
                                               'name': v})[0].data
                    if result['uses_remaining'] != 0:
                        buffList.append(k)
                if buffList:
                    return "Buffs available: {}.".format(', '.join(buffList))
                return "No buffs available to {}.".format(msg['userName'])
            buffName = args.strip().lower()
            if buffName not in self._buffs:
                return "Unknown buff '{}'.".format(buffName)
            try:
                result = self._raiseEvent(
                            'buff', self._buffer, 
                            {'userId': msg['userId'], 
                            'name': self._buffs[buffName]})[0].data
            except Exception as e:
                    return "An error occurred: {}".format(e)
            if result['success']:
                return ""
            elif result['uses_remaining'] == 0:
                return ("Sorry, you've hit today's limit for {}."
                        .format(buffName))
            else:
                return ("Sorry, there was an error with your buff: {}"
                        .format(result['error']))
        return None

    def _availableCommands(self):
        return {'buff': "!buff: Request a buff or get a list of available "
                        "buffs."}
