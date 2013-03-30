import re
from cwbot.modules.BaseChatModule import BaseChatModule
from cwbot.util.textProcessing import listToString, stringToList


class KeywordModule(BaseChatModule):
    """ This is a special module that can be assigned a variable command-
    name, specified by the command and helptext configuration options.
    When invoked, it takes the argument and replies with a string based
    on argument matching. The special entry __default__ is used when no
    arguments are supplied, __error__ is used if no match is found, and
    __unique__ if multiple matches are found.
    The special string %keywords% is replaced with a comma-separated list of
    all available keywords, %arg% is replaced with the argument called, and
    %num% with the number of matches (for __unique__ only).
    Note: you can specify multiple commands in a comma-separated list.
    
    Configuration example:
    [[[Rules-Module]]]
        type = KeywordModule
        priority = 10
        command = rules
        helptext = !rules RULENAME shows clan rules.
        [[[[text]]]]
            __default__ = I have rules for the following: %keywords%
            __error__ = I can't find a rule for %arg%.
            __unique__ = Your query %arg% matched more than one result (%num%).
            hobopolis = Make sure you are in clan chat!
            slimetube = No squeezing gallbladders!
        
    Example usage:
    Player> !rules
    Bot> I have rules for the following: hobopolis, slimetube
    Player> !rules hobopolis
    Bot> Make sure you are in clan chat!
    Player> !rules stash
    Bot> I can't find a rule for stash.
    """
    
    requiredCapabilities = ['chat']
    _name = "keyword"
    

    def _availableCommands(self):
        ac = dict((c, None) for c in self._command)
        ac[self._command[0]] = self._helpText
        return ac
        
    
    def __init__(self, manager, identity, config):
        self._rules = {}
        self._command = None
        self._helpText = None
        super(KeywordModule, self).__init__(manager, identity, config)


    def _configure(self, config):
        self._command = map(
                str.lower, stringToList(config.get('command', 'UNCONFIGURED')))
        config['command'] = listToString(self._command)
        
        self._helpText = config.setdefault('helptext', 'UNCONFIGURED')
        
        ruleDict = config.get('text', {})
        ruleDict.setdefault('__default__', "Ask me about: %keywords%.")
        ruleDict.setdefault('__error__', "I don't know anything about %arg%.")
        ruleDict.setdefault('__unique__', 
                            "I don't have a unique match for %arg%.")
        config['text'] = ruleDict
        
        for keyword,rule in ruleDict.items():
            self._rules[keyword.strip().lower()] = rule.decode('string_escape')
        self.debugLog("Added {} keyword-rules.".format(len(self._rules)))

        
    def _processCommand(self, msg, cmd, args):
        if cmd in self._command:
            rules = []
            simplify = lambda x: ''.join(re.split(r'\W+', x.strip())).lower() 
            if args.strip() == "":
                rules.append(self._rules['__default__'])
            else:
                query = simplify(args)
                for key,rule in self._rules.items():
                    k = simplify(key)
                    if not key.startswith("__") and (k in query or query in k):
                        rules.append(rule)
            if len(rules) == 1:
                return self._annotate(rules[0], args)
            elif len(rules) > 1:
                rule = self._rules.get('__unique__', self._rules['__error__'])
                rule = rule.replace("%num%", str(len(rules)))
                return self._annotate(rule, args)
            return self._annotate(self._rules['__error__'], args)
        return None

    
    def _annotate(self, rule, args):
        rule = rule.replace("%arg%", args)
        rule = rule.replace("%keywords%", 
                            ', '.join(item for item in self._rules.keys()
                                      if not item.startswith("__")))
        return rule

