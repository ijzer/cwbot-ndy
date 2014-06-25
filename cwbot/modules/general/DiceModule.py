import re
import random
from cwbot.modules.BaseChatModule import BaseChatModule
from cwbot.util.shuntingYard import evalInfix


def parseDice(args):
    """ Parse a dice expression (e.g., 3d10-1d6) and evaluate the dice
    (e.g., to the string 18-2) """
    m = re.search(r'(\d*)d(\d+)', args)
    while m is not None:
        total = 0
        qty = 1 if m.group(1) is "" else int(m.group(1))
        val = int(m.group(2))
        if qty > 100:
            # prevent abusive requests
            raise ValueError("I can't hold {} dice in my robotic hands!"
                             .format(qty))
        if val == 0:
            raise ValueError("A zero-sided die! "
                             "Quite the existential conundrum.")
        if val < 0:
            raise ValueError("You want me to roll a die with negative sides?")
        for _i in range(qty):
            total += random.randint(1, val)
        args = args[:m.start()] + " " + str(total) + " " + args[m.end():]
        m = re.search(r'(\d*)d(\d+)', args)
    return args
        
        
class DiceModule(BaseChatModule):
    """ 
    A dice-rolling module capable of rolling arbitrary dice sequences and
    permuting lists. Also can be used for math, oddly enough.
    
    No configuration options.
    """
    
    requiredCapabilities = ['chat']
    _name = "dice"
        

    def _processCommand(self, message, cmd, args):
        if cmd in ["roll", "dice"]:
            if args.strip() == "":
                return self._availableCommands()['roll']
            # default manager ignores all text after (); for example
            # !roll (10)+1d5 is interpreted as !roll 10. Here we extract
            # the full argument from the message by removing the first
            # word, and then testing if that works.
            s = message.get('text', "")
            splitStr = re.split(r'([\s(])', s)
            fullArgs = (''.join(word for word in splitStr[1:])).strip()
            (replyStr, success) = self.rollDice(fullArgs)
            # if success == False, try again with just args. A return of false
            # either indicates an evaluation error, or that the input was
            # interpreted as a list. Either way, we want to just use args.
            if success:
                return replyStr
            (replyStr2, success2) = self.rollDice(args)
            if success2:
                return replyStr2
            
            # failed. just return the original failure message.
            return replyStr
        if cmd in ["order", "permute", "permutation"]:
            if args.strip() == "":
                return self._availableCommands()['permute']
            return self.rollOrder(args)
        return None
    
    
    def getNameList(self, args):
        """ Split a list into its elements (e.g., "a,b,c" -> ['a', 'b', 'c'])
        """
        nList = re.split(r'\s*,\s*', args)
        self.debugLog("found names: {}".format(nList))
        return [name for name in nList if len(name) > 0]

    
    def rollMdN(self, args):
        """ roll a set of "XdX+XdX-XdX etc...
        returns a tuple: (outputString, successBool) """
        args = args.replace(" ", "")
        returnStr = args
        try:
            # first, roll the dice
            argsRolled = parseDice(args).strip()
            # add to result chain
            if args != argsRolled:
                returnStr += " -> " + argsRolled
        except ValueError as e:
            # return the error
            returnStr += " -> " + e.args[0]
            return (returnStr, False)
        try:
            # now, evaluate the expression
            argsEvaluated = evalInfix(argsRolled, self.properties.debug)
            # add to result chain
            if argsRolled != str(argsEvaluated):
                returnStr += " -> {:g}".format(argsEvaluated)
        except (ValueError, ZeroDivisionError, OverflowError) as e:
            # return error
            returnStr += " -> Evaluation error ({})".format(e.args[0])
            return (returnStr, False)
        return (returnStr, True)
    
    
    def rollOrder(self, args):
        """ permute a list """
        names = []
        maxLength = 100
        try:
            # convert !permute 10 to !permute 1,2,3,4,5,6,7,8,9,10
            n = int(re.findall(r'^\d+[^,]*$', args)[0])
            if n > maxLength:
                return "I'm not permuting that many things!"
            names = [str(num+1) for num in range(n)]
        except (ValueError, IndexError):
            names = self.getNameList(args)
        
        self.debugLog("Received names {}".format(names))
        if names is None or len(names) == 0:
            return ("I couldn't understand your permute request. See !help "
                    "permute for format options.")
        if len(names) == 1:
            return ("It doesn't make much sense to randomly permute a list "
                    "of one item.")
        if len(names) > maxLength:
            return "I can't keep track of all that!"
        random.shuffle(names)
        return ', '.join(names)
        
    
    def rollDice(self, args):
        """ returns a tuple: (outputString, diceSuccessBool)
        diceSuccessBool is True if the input was interpreted as a
        dice expression and was successful. It returns false if there
        was an evaluation error, OR if args is interpreted as a list of
        names. """
        try:
            # if expression is !roll N, change to !roll 1dN
            m = re.search(r'^(\d+)$', args)
            if m is not None:
                n = int(m.group(1))
                self.debugLog("Rolling a d{}".format(n))
                return self.rollMdN("1d{}".format(n))
        except (ValueError, IndexError):
                pass

        names = self.getNameList(args)
        if names is None or len(names) == 0:
            # if no names available, try evaluating the expression
            return self.rollMdN(args)
        if len(names) == 1:
            # only one name found? try evaluating it
            return self.rollMdN(args)

        n = random.randint(0, len(names)-1)
        self.debugLog("Selecting {} out of {}".format(n, str(names)))
        returnStr = "{} (out of {} entries)".format(names[n], len(names))
        return (returnStr, False)


    def _availableCommands(self):
        return {'roll': "!roll: Use '!roll N' to roll a dN "
                        "(also allowed: !roll MdN or !roll MdN+OdP). "
                        "Use '!roll name1,name2,...' to select a name. "
                        "See also !permute.", 
                'permute': "!permute: Use '!permute N' to generate a "
                           "permutation from 1 to N, or '!permute "
                           "name1,name2,...' to assign a list order. "
                           "See also !roll.",
                'dice': None, 'order': None, 'permutation': None}
