import abc
import math
import copy
import weakref
from kol.request.StoreRequest import StoreRequest
from kol.request.UseItemRequest import UseItemRequest
from kol.request.CampgroundRestRequest import CampgroundRestRequest
from kol.request.UseSkillRequest import UseSkillRequest
from kol.request.StatusRequest import StatusRequest
from kol.request.EatFoodRequest import EatFoodRequest
from kol.database.SkillDatabase import getSkillFromId
import kol.Error
from cwbot.common.exceptions import FatalError
from cwbot.kolextra.request.GalaktikRequest import GalaktikRequest
from cwbot.kolextra.request.GalaktikBuyRequest import GalaktikBuyRequest
from cwbot.modules.BaseModule import BaseModule
from cwbot.locks import InventoryLock 
from cwbot.util.tryRequest import tryRequest



def toTypeOrNone(val, type_):
    if val is None:
        return None
    if str(val).lower() in ["''", '""', "none", ""]:
        return None
    return type_(val)


class _Healer(object):
    """ Object that is responsible for healing with its heal() method.
    If healing cannot be achieved, just return from the function and do
    nothing. 
    """
    def __init__(self, parent, args):
        minHeal = args.setdefault('only_heal_over', 0)
        try:
            self._minHealAmount = int(minHeal)
        except ValueError:
            raise FatalError("{}: Invalid only_heal_over value: {}"
                             .format(self.parent.id, minHeal))
        self.parent = weakref.proxy(parent)
    
    @abc.abstractmethod
    def heal(self, hint, args, status):
        pass

    @property
    def minMp(self):
        return 0
    
    @property
    def minHeal(self):
        return self._minHealAmount

    @abc.abstractmethod
    def __str__(self):
        pass
    
    
class _ItemHealer(_Healer):
    def __init__(self, parent, args):
        self._itemMaxHealPoints = None
        self._seen = 0
        
        super(_ItemHealer, self).__init__(parent, args)
        itemId = args.setdefault('id', "UNKNOWN")
        try:
            self.id = int(itemId)
        except ValueError:
            raise FatalError("{}: Invalid item id: {}"
                             .format(self.parent.id, itemId))
        self.buyFrom = toTypeOrNone(args.setdefault('buy_from', "none"), str)
        
    def __str__(self):
        return ("Item {}; buy={}; min={}"
                .format(self.id, self.buyFrom, self.minHeal))
        
    def heal(self, hint, args, status):
        currentVal = status[args['type']]
        n = 1
        if self._seen > 10:
            maxPotential = self._itemMaxHealPoints * 1.1
            n = int(max(1, math.floor(hint/maxPotential)))
        with InventoryLock.lock:
            invMan = self.parent.inventoryManager
            invMan.refreshInventory()
            inv = invMan.inventory()
            qtyInInventory = inv.get(self.id, 0) 
            if qtyInInventory == 0:
                if self.buyFrom is None:
                    self.parent.log("Out of item {}".format(self.id))
                    return
            if qtyInInventory < n:
                if self.buyFrom is not None:
                    r1 = StoreRequest(self.parent.session, 
                                      self.buyFrom, 
                                      self.id,
                                      quantity=(n-qtyInInventory))
                    tryRequest(r1, nothrow=True, numTries=1)
                    invMan.refreshInventory()
                    inv = invMan.inventory()
                    qtyInInventory = inv.get(self.id, 0) 
                    if qtyInInventory == 0:
                        self.parent.log("Couldn't buy item {}".format(self.id))
                        return
            r2 = UseItemRequest(self.parent.session, self.id)
            try:
                toUse = min(n, qtyInInventory)
                for _ in range(toUse):
                    tryRequest(r2, numTries=1)

                # update "best seen value"
                if toUse == 1:
                    status = self.parent.hpMpStatus()
                    newVal = status[args['type']]
                    if (newVal != status['max' + args['type']] 
                            and newVal > currentVal):
                        self._seen += 1
                        self._itemMaxHealPoints = max(self._itemMaxHealPoints, 
                                                      newVal - currentVal)
                        self.parent.log("New estimate for {}: heals {} {}"
                                        .format(self, 
                                                self._itemMaxHealPoints,
                                                args['type']))
            except kol.Error.Error:
                self.parent.log("Failed to use item {}".format(self.id))
            

class _RestHealer(_Healer):
    def __init__(self, parent, args):
        super(_RestHealer, self).__init__(parent, args)
        self._restMaxHealPoints = None
        self._seen = 0

    def heal(self, hint, args, status):
        currentVal = status[args['type']]
        n = 1
        if self._seen > 10:
            maxPotential = self._restMaxHealPoints * 1.1
            n = int(max(1, math.floor(hint/maxPotential)))
        r1 = CampgroundRestRequest(self.parent.session)
        try:
            self.parent.log("Resting {} times...".format(n))
            for _ in range(n):
                tryRequest(r1, numTries=1)

            # update "best seen value"
            if n == 1:
                status = self.parent.hpMpStatus()
                newVal = status[args['type']]
                if (newVal != status['max' + args['type']] 
                        and newVal > currentVal):
                    self._seen += 1
                    self._restMaxHealPoints = max(self._restMaxHealPoints, 
                                                  newVal - currentVal)
                    self.parent.log("New estimate for {}: heals {} {}"
                                    .format(self, 
                                            self._restMaxHealPoints,
                                            args['type']))
        except kol.Error.Error:
            self.parent.log("Failed to rest")
        
    def __str__(self):
        return "Rest; min={}".format(self.minHeal)
        
        
class _SkillHealer(_Healer):
    def __init__(self, parent, args):
        self._skillMaxHealPoints = None
        self._seen = 0
        
        super(_SkillHealer, self).__init__(parent, args)
        skillId = args.setdefault('id', "UNKNOWN")
        try:
            self.id = int(skillId)
        except ValueError:
            raise FatalError("{}: Invalid skill id: {}"
                             .format(self.parent.id, skillId))
        if 'required_mp' not in args:
            try:
                skill = getSkillFromId(str(self.id), parent.session)
                args['required_mp'] = skill['mpCost']
            except kol.Error.Error:
                args['required_mp'] = "UNKNOWN"
        try:
            self._mpCost = int(args['required_mp'])
        except ValueError:
            raise FatalError("{}: Invalid mp cost: {}"
                             .format(self.parent.id, args['required_mp']))
        try:
            self.typicalCasts = int(args.setdefault(
                                                'typical_number_casts', '1'))
        except ValueError:
            raise FatalError("{}: Invalid typical casts: {}"
                             .format(self.parent.id, args[
                                                    'typical_number_casts']))

    @property
    def minMp(self):
        if self._seen > 10:
            return self._mpCost * self.typicalCasts
        return self._mpCost
        
    def heal(self, hint, args, status):
        currentVal = status[args['type']]
        n = 1
        if self._seen > 10:
            maxPotential = self._skillMaxHealPoints * 1.1
            n = int(max(1, math.floor(hint/maxPotential)))
            n = min(n, int(math.floor(status['mp']/float(self._mpCost))))
        r1 = UseSkillRequest(self.parent.session, str(self.id), numTimes=n)
        try:
            tryRequest(r1, numTries=1)

            # update "best seen value"
            if n == 1:
                status = self.parent.hpMpStatus()
                newVal = status[args['type']]
                if (newVal != status['max' + args['type']] 
                        and newVal > currentVal):
                    self._seen += 1
                    self._skillMaxHealPoints = max(self._skillMaxHealPoints, 
                                                  newVal - currentVal)
                    self.parent.log("New estimate for {}: heals {} {}"
                                    .format(self, 
                                            self._skillMaxHealPoints,
                                            args['type']))
        except kol.Error.Error as e:
            self.parent.log("Error using {}: {}".format(self, e[0]))
        
    def __str__(self):
        return ("Skill {}; mp={}; minHP={}"
                .format(self.id, self.minMp, self.minHeal))  
    
    
class _LuciferHealer(_Healer):
    def __init__(self, parent, args):
        super(_LuciferHealer, self).__init__(parent, args)
        self.extHealer = toTypeOrNone(
                            args.setdefault('external_healer', 'none'), str)
        try:
            self.maxFull = toTypeOrNone(args.setdefault('max_full', 'none'), 
                                        int)
        except ValueError:
            raise FatalError("Invalid max_full value for Lucifer: {}"
                             .format(args['max_full']))
        
    def __str__(self):
        return ("Lucifer; external={}; maxfull={}, min={}"
                .format(self.extHealer, self.maxFull, self.minHeal))
        
    def heal(self, hint, args, status):
        if args.get('__lucifer__', False):
            self.parent.log("Skipping Lucifer (no recursive Lucifer allowed)")
            return
        with InventoryLock.lock:
            invMan = self.parent.inventoryManager
            invMan.refreshInventory()
            inv = invMan.inventory()
            if inv.get(571, 0) == 0:
                self.parent.log("Out of Lucifers.")
                return
            r1 = StatusRequest(self.parent.session)
            d1 = tryRequest(r1)
            if self.maxFull is not None and int(d1['full']) >= self.maxFull:
                self.parent.log("Reached reserve fullness.")
                return
            mpToHeal = status['maxmp'] - status['mp']
            hpNeeded = min(1 + (mpToHeal/9 + 1), status['maxhp'])
            self.parent.log("Lucifer: requires {} hp, have {} hp."
                            .format(hpNeeded, status['hp']))
            if hpNeeded > status['hp']:
                curHp = None
                self.parent.log("Healing for Lucifer...")
                if self.extHealer is None:
                    reply = self.parent._heal({'type': 'hp', 
                                               'amount': hpNeeded, 
                                               'unit': 'points',
                                               '__lucifer__': True})
                    curHp = reply['hp']
                else:
                    replies = self.parent._raiseEvent(
                                "heal", "__" + self.extHealer + "__", 
                                {'type': 'hp', 
                                 'amount': hpNeeded, 
                                 'unit': 'points',
                                 '__lucifer__': True})
                    curHp = replies[-1]['hp']
                if curHp < hpNeeded:
                    self.parent.log("Failed to heal for Lucifer.")
                    return
                self.parent.log("Healed for Lucifer!")
            r2 = EatFoodRequest(self.parent.session, 571)
            try:
                tryRequest(r2, numTries=1)
            except kol.Error.Error as e:
                self.parent.log("Lucifer error: {}".format(e[0]))            


class _GalaktikHealer(_Healer):
    def __init__(self, parent, args):
        super(_GalaktikHealer, self).__init__(parent, args)
        self.type = args.setdefault('method', "UNKNOWN")
        if self.type not in ['ointment', 'tonic', 'nostrum']:
            raise KeyError("Invalid Galaktik Healer method: {}. Must be one "
                           "of ointment, tonic, nostrum".format(self.type))
        
    def __str__(self):
        return "Galaktik {}; min={}".format(self.type, self.minHeal)
    
    def heal(self, hint, args, status):
        if self.type == 'tonic':
            rMp = GalaktikRequest(self.parent.session, False, hint)
            tryRequest(rMp)
            return
        elif self.type == 'nostrum':
            rHp = GalaktikRequest(self.parent.session, True, hint)
            tryRequest(rHp)
            return
        with InventoryLock.lock:
            n = int(max(1, math.floor(hint/10.0)))
            invMan = self.parent.inventoryManager
            invMan.refreshInventory()
            inv = invMan.inventory()
            myQty = inv.get(232, 0)
            if myQty < n:
                rBuy = GalaktikBuyRequest(self.parent.session, 232, n - myQty)
                tryRequest(rBuy, nothrow=True)
            rUse = UseItemRequest(self.parent.session, 232)
            try:
                for _ in range(n):
                    tryRequest(rUse)
            except kol.Error.Error:
                pass


class HealingModule(BaseModule):
    """ 
    An internal module that allows other modules to use healing.
    To heal: raise an event with the subject "heal" and the following data
    dictionary:
    
    {'type': 'mp', 'amount': 90, 'unit': 'points'}
    type should be 'hp' or 'mp'
    amount should be an integer
    unit specifies how 'amount' in interpreted; either 'percent' or 'points'
    Note that these units are ABSOLUTE: the above data means that the
    HealingModule should restore the bot to at least 90 MP. If you want to
    heal 90 MP more than you currently have, do a StatusRequest to get your
    current MP, then add 90. The same works for percent specifications.
    The module will reply with the data 
    {'hp': new_hp, 'mp': new_mp, 'maxhp': max_hp, 'maxmp': max_mp}. The
    module will not throw if it fails to heal, so be sure to actually check
    that healing has worked! You should use the code structure:
    
    replies = self._raiseEvent('heal', {'type': 'hp', 
                                        'amount': '50',
                                        'unit': 'points'}) # your command here
    curHp = replies[-1]['hp']
    
    to check HP/MP.

    Note that it's possible to load more than one healing module, so you
    can configure different healing methods for different modules, provided
    they support that option, by specifying an event identity target. If you
    don't specify a target, you will get multiple replies (but, if the first
    succeeds, the others will have nothing to do!)
    
    TYPES OF HEALING NOT YET SUPPORTED:
    nuns, hot tub/april shower, free rests, buying from mall
    
    To configure: use the following format:

    [[[Healing1]]]
        type = core.HealingModule
        [[[[hp]]]]
            #### priority list of ways to restore HP
            external_mp_healer = none
            # optional secondary module to restore MP for HP skills
            [[[[[1]]]]]
                type = skill # possible types: item, skill, rest, galaktik
                id = 3012 # Cannelloni Cocoon
                # bot heals to this much MP to use. Tries to auto-detect
                required_mp = 20 
                only_heal_over = 116 # only use to heal more than X HP or MP
            [[[[[2]]]]]
                type = skill
                required_mp = 12
                id = 3009 # Lasagna Bandages
            [[[[[3]]]]]
                type = galaktik
                method = ointment # possible methods: ointment, tonic, nostrum
            [[[[[4]]]]]
                type = galaktik
                method = nostrum
        [[[[mp]]]]
            #### priority list of ways to restore MP
            [[[[[1]]]]]
                # PYEC from inventory
                type = item # possible types: item, lucifer, rest, galaktik
                buy_from = none # store letter or "none"
                id = 1687 # PYEC
                only_heal_over = 100 # only use to heal more than X HP or MP 
            [[[[[2]]]]]
                # dr. lucifer
                type = lucifer
                external_healer = none
                # NOTE: healing is done before using Dr. Lucifer. It's
                # possible to use a HealingModule with a different identity
                # using external_healer.
                max_full = 99 # use this to reserve any fullness for bot
                only_heal_over = 100
            [[[[[3]]]]]
                # MMJ (from grocery)
                type = item
                buy_from = 2 # name of the grocery (check kol/StoreRequest.py)
                id = 518
            [[[[[4]]]]]
                # black cherry soda (from black market)
                type = item
                buy_from = l
                id = 2639
            [[[[[5]]]]]
                # Knob Goblin seltzer (from dispensary)
                type = item
                buy_from = k
                id = 344
            [[[[[6]]]]]
                type = galaktik
                method = tonic
            [[[[[7]]]]]
                type = rest
    """
    requiredCapabilities = ['inventory']
    _name = "healing"
    
    _healers = {'item': _ItemHealer,
                'rest': _RestHealer,
                'skill': _SkillHealer,
                'lucifer': _LuciferHealer,
                'galaktik': _GalaktikHealer}

    def __init__(self, manager, identity, config):
        self._hpMethods = []
        self._mpMethods = []
        super(HealingModule, self).__init__(manager, identity, config)

        
    def _configure(self, config):
        self._hpMethods = []
        self._mpMethods = []
        self._hp = config.setdefault('hp', 
                      {'external_mp_healer': 'none',
                       '1': {'type': 'skill',
                             'id': 3012,
                             'required_mp': 20,
                             'only_heal_over': 116},
                       '2': {'type': 'skill',
                             'required_mp': 12,
                             'id': 3009},
                       '3': {'type': 'galaktik',
                             'method': 'ointment'},
                       '4': {'type': 'rest'}})
        self._mp = config.setdefault('mp',
                       {'1': {'type': 'item',
                              'buy_from': 'none',
                              'id': 1687,
                              'only_heal_over': 100},
                        '2': {'type': 'lucifer',
                              'external_healer': 'none',
                              'max_full': 'none',
                              'only_heal_over': 100},
                        '3': {'type': 'item',
                              'buy_from': '2',
                              'id': 518},
                        '4': {'type': 'item',
                              'buy_from': 'l',
                              'id': 2639},
                        '5': {'type': 'item',
                              'buy_from': 'k',
                              'id': 344},
                        '6': {'type': 'galaktik',
                              'method': 'tonic'}})
        self._extMp = None
        extMp = toTypeOrNone(self._hp['external_mp_healer'], str)
        if extMp is not None:
            self._extMp = "__" + extMp.lower() + "__"
        hpPriorities = dict((int(k), v) for k,v in self._hp.items()
                            if k.isdigit()) 
        mpPriorities = dict((int(k), v) for k,v in self._mp.items()
                            if k.isdigit()) 
        for p in sorted(hpPriorities.keys()):
            self._hpMethods.append(self._createHealer(hpPriorities[p]))
        for p in sorted(mpPriorities.keys()):
            self._mpMethods.append(self._createHealer(mpPriorities[p]))
            
            
    def _createHealer(self, params):
        className = params['type']
        classFactory = self._healers[className]
        return classFactory(self, params)
    
    
    def hpMpStatus(self):
        rStat = StatusRequest(self.session)
        dStat = (self.tryRequest(rStat))
        return {'hp': int(dStat['hp']), 'mp': int(dStat['mp']),
                'maxhp': int(dStat['maxhp']), 'maxmp': int(dStat['maxmp'])}
    
    
    def _heal(self, healData):
        healerList = None
        healType = healData['type']
        if healType == 'hp':
            healerList = copy.copy(self._hpMethods)
        elif healType == 'mp':
            healerList = copy.copy(self._mpMethods)
        else:
            raise KeyError("Invalid healing type: {}".format(healType))
        healUnit = healData['unit']
        healTo = None
        status = self.hpMpStatus()
        maxval = status['max' + healType]
        if healUnit == 'points' or healUnit == 'point':
            healTo = min(maxval, int(healData['amount']))
        elif healUnit == 'percent':
            percent = min(int(healData['amount']), 100)
            healTo = int(math.floor(percent / 100.0 * maxval))
        else:
            raise KeyError("Invalid healing unit: {}".format(healUnit))
        
        curPoints = status[healType]
        self.log("--- Requested healing to {0} {1}, current {1} = {2} ---"
                  .format(healTo, healType, curPoints))
        self.debugLog("Healing with the following: {}"
                      .format(", then ".join(map(str, healerList))))
        while curPoints < healTo:
            self.debugLog("Current {} = {}; continuing to heal."
                          .format(healType, curPoints))
            if healerList:
                myHealer = healerList[0]
                self.debugLog("Trying healer {}".format(myHealer))
                pointsToGo = healTo - curPoints
                if pointsToGo >= myHealer.minHeal:
                    self.log("Healing with {}...".format(myHealer))
                    if healType == 'hp' and status['mp'] < myHealer.minMp:
                        self.log("Not enough mp to use {}; healing to {} mp"
                                  .format(myHealer, myHealer.minMp))
                        newData = copy.deepcopy(healData)
                        newData.update(
                            {'type': 'mp', 
                             'amount': myHealer.minMp,
                             'unit': 'points'})
                        reply = None
                        if self._extMp is None:
                            reply = self._heal(newData)
                        else:
                            replies = self._raiseEvent("heal", 
                                                       self._extMp, 
                                                       newData)
                            reply = replies[-1]
                        status = self.hpMpStatus()
                        curPoints = status[healType]
                        self.log("Done restoring mp.")
                    myHealer.heal(healTo - curPoints, healData, status)              
                    status = self.hpMpStatus()
                    newPoints = status[healType]
                    if newPoints == curPoints:
                        # failed to heal
                        healerList.pop(0)
                        self.log("No change in {}".format(healType))
                    else:
                        self.log("Healed to {} hp / {} mp"
                                  .format(status['hp'], status['mp']))
                    curPoints = newPoints
                else:
                    self.log("Skipping {}; not enough points to heal "
                              "(requires {} {})"
                              .format(myHealer, myHealer.minHeal, healType))
                    healerList.pop(0)
            else:
                self.log("Failed to heal completely.")
                break
        status = self.hpMpStatus()
        self.log("--- Done healing! Final values: {}/{} hp; {}/{} mp ---"
                  .format(status['hp'], status['maxhp'], 
                          status['mp'], status['maxmp']))
        return status
        
        
    def _eventCallback(self, eData):
        if eData.subject == "state":
            self._eventReply(self.state)    
        elif eData.subject == "heal":
            statusTag = self._heal(eData.data)
            self._eventReply(statusTag)
