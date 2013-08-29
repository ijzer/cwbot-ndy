import time
import random
from math import floor
import calendar
from collections import defaultdict
import threading
import copy
from cwbot.kolextra.request.ClanDetailedMemberRequest \
                     import ClanDetailedMemberRequest
from cwbot.modules.BaseModule import BaseModule
from cwbot.kolextra.request.UserProfileRequest import UserProfileRequest
from kol.request.ClanWhitelistRequest import ClanWhitelistRequest
from cwbot.kolextra.request.ClanChangeRankRequest import ClanChangeRankRequest
from kol.request.AddPlayerToClanWhitelistRequest \
          import AddPlayerToClanWhitelistRequest
from cwbot.kolextra.request.RemovePlayerFromClanWhitelistRequest \
                     import RemovePlayerFromClanWhitelistRequest
from kol.request.BootClanMemberRequest import BootClanMemberRequest
from cwbot.common.exceptions import FatalError
from kol.request.StatusRequest import StatusRequest
from cwbot.util.textProcessing import toTypeOrNone, stringToBool, stringToList
from cwbot.common.kmailContainer import Kmail


# standardize a rank name by converting it to lower case and removing spaces
def _rankTransform(rank):
    if rank == "(none)":
        rank = "Normal Member"
    return "".join(rank.lower().strip().split())


def _secsToDays(n):
    return int(floor(n / 86400.0))


def _daysToSecs(n):
    return int(n * 86400)

class ClanRankModule(BaseModule):
    """ 
    A module that handles clan rank promotions and demotions, as well
    as booting users for inactivity. The promotions/demotions/booting routine
    is run once per day at a random time to avoid slamming the KoL servers
    with tons of requests.
    
    Configuration format:
    
    [[[Ranks]]]
        type = ClanRankModule
        priority = 10
        permission = None
        clan_only = False
        boot_after_days = 180 # set to 0 for no booting
        safe_ranks = unbootable_rank_1, unbootable_rank_2
        safe_titles = unbootable_title_1, unbootable_title_2
        # set below to none for no message
        boot_message = You have been booted for inactivity.
        simulate = false # if true, do not actually boot/promote users
        # do not set this to true if your bot runs 24/7
        run_immediately = false
        boot_every_n_days = 1
        [[[[rules]]]]
            [[[[[Normal Member]]]]]
                # karma requirement for this rank
                min_karma = 0
                # can a user with this rank be demoted if they lose karma?
                demotion_allowed = False
                # next rank in the chain
                next_rank = RankName2  
                # minimum time that must be spent in this rank
                min_days_until_next_promotion = 0
                # total number of days in clan before this rank can be granted
                min_days_in_clan = 0
            [[[[[RankName2]]]]]
                min_karma = 0
                demotion_allowed = False
                next_rank = none # end of chain 
                min_days_until_next_promotion = 0
                min_days_in_clan = 0

    """
    requiredCapabilities = ['chat']
    _name = "clan-rank"


    def __init__(self, manager, identity, config):
        self._inactiveAstrals = None
        self._ruleConfig = None
        self._userDb = None
        self._ranks = None
        self._inactivityDays = None
        self._rolloverTime = None
        self._lastRun = None
        self._promotionRules = None
        self._execTime = None
        self._immediate = None
        self._bootFrequencyDays = None
        self._doFinishInit = threading.Event()
        self._titles = {}
        self._safeRanks = self._safeTitles = None
        self._stopNow = threading.Event()
        self._running = threading.Event()
        super(ClanRankModule, self).__init__(manager, identity, config)
        
        
    def _configure(self, config):
        self._daysUntilBoot = int(config.setdefault('boot_after_days', 180))
        safeRanks = stringToList(config.setdefault('safe_ranks',
                                                   "rank1, rank2"))
        safeTitles = stringToList(config.setdefault('safe_titles',
                                                    "DO NOT DELETE, "
                                                    "DO NOT ERASE"))
        self._safeRanks = map(_rankTransform, safeRanks)
        self._safeTitles = map(_rankTransform, safeTitles)
        self._bootMessage = toTypeOrNone(config.setdefault('boot_message',
                                                           "none"))
        self._simulate = stringToBool(config.setdefault('simulate', "false"))
        self._immediate = stringToBool(config.setdefault('run_immediately',
                                                         "false"))
        try:
            self._bootFrequencyDays = int(config.setdefault(
                                                    'boot_every_n_days', 1))
        except ValueError:
            raise FatalError("ClanRankModule: boot_every_n_days must "
                             "be integral")

        rules = config.setdefault('rules', 
                        {'Normal Member': {'demotion_allowed': "false",
                                   'min_karma': 0,
                                   'min_days_until_next_promotion': 7,
                                   'min_days_in_clan': 0,
                                   'next_rank': 'Rank2'},
                         'Rank2': {'demotion_allowed': "true",
                                   'min_karma': 0,
                                   'min_days_until_next_promotion': 0,
                                   'min_days_in_clan': 0,
                                   'next_rank': "none"}})
        
        for rule in rules.values():
            rule.setdefault('demotion_allowed', True)
            rule.setdefault('min_karma', 0)
            rule.setdefault('min_days_until_next_promotion', 0)
            rule.setdefault('min_days_in_clan', 0)
            rule.setdefault('next_rank', "none")
        
        self._ruleConfig = rules
        
        
    def initialize(self, state, initData):
        self._userDb = state['userDb']
        self._lastRun = state.get('lastRun', 0)
        self._inactiveAstrals = state.get('inactiveAstrals', {})
        # initialization will be finished in the first heartbeat thread.
        # we do NOT want anything that could throw an exception here! That
        # would reset the state
        self._doFinishInit.set()
        
        
    def _finishInitialization(self):
        # get list of clan members (both in whitelist and roster)
        self.log("Initializing ranks...")
        r1 = ClanWhitelistRequest(self.session)
        d1 = self.tryRequest(r1)
        self._ranks = {_rankTransform(rank['rankName']): rank 
                       for rank in d1['ranks']}
        r2 = StatusRequest(self.session)
        d2 = self.tryRequest(r2)
        self._rolloverTime = int(d2['rollover'])
        
        # load promotion rules
        self._promotionRules = {}
        for rankname,rule in self._ruleConfig.items():
            key = _rankTransform(rankname)
            nextRankName = toTypeOrNone(rule['next_rank'])
            nextkey = _rankTransform(nextRankName) if nextRankName else None
            nextRankId = self._ranks.get(nextkey, {}).get('rankId')
            
            if key not in self._ranks:
                raise FatalError("Invalid clan rank: {} (available ranks: {})"
                                 .format(key, ", ".join(self._ranks.keys())))
            if nextkey is not None and nextkey not in self._ranks:
                raise FatalError("Invalid clan rank: {} (available ranks: {})"
                                 .format(nextkey, 
                                         ", ".join(self._ranks.keys())))

            try:                
                self._promotionRules[self._ranks[key]['rankId']] = (
                    {'demotionAllowed': stringToBool(rule['demotion_allowed']),
                     'minKarma': int(rule['min_karma']),
                     'minDaysBeforePromotion': 
                                int(rule['min_days_until_next_promotion']),
                     'minDaysInClan': int(rule['min_days_in_clan']),
                     'nextRankId': nextRankId,
                     'rankName': rankname})
            except ValueError:
                raise "ClanRankModule: error parsing rank {}".format(rankname)
        
        # pick a random time to run today
        assumedExecTime = 7200
        latestPossibleExecTime = self._rolloverTime - assumedExecTime
        if time.time() < self._lastRun:
            self.log("Already performed ranking today.")
        elif time.time() > latestPossibleExecTime:
            self.log("Too late to run rankings today.")
        else:
            if self._immediate:
                self._execTime = int(time.time()) + 15
            else:
                self._execTime = random.randint(int(time.time()), 
                                                latestPossibleExecTime)
            self.log("Running rankings in {} minutes."
                     .format(int((self._execTime - time.time()) / 60)))

    
    @property
    def initialState(self):
        return {'userDb': {},
                'lastRun': 0,
                'inactiveAstrals': {}}
    
    
    @property
    def state(self):
        return {'userDb': self._userDb,
                'lastRun': self._lastRun,
                'inactiveAstrals': self._inactiveAstrals}
        
        
    def _runTasks(self):
        self._running.set()
        if not self._stopNow.is_set():
            self._doPromotionDemotion(self._simulate)
        if not self._stopNow.is_set():
            self._updateInactiveAstrals()
        if not self._stopNow.is_set():
            day = time.gmtime(self._rolloverTime).tm_yday
            sequenceDay = day % self._bootFrequencyDays
            if sequenceDay == 0:
                self._doBooting(self._simulate)
            else:
                self.log("Performing booting in {} days."
                         .format(self._bootFrequencyDays - sequenceDay))
        if not self._stopNow.is_set():
            self._lastRun = self._rolloverTime
        self._running.clear()


    # update the database of clan members
    def _refreshClanMembers(self):
        self.debugLog("Fetching clan member list...")
        
        curTime = int(time.time())
        newUserDb = copy.deepcopy(self._userDb)
        for record in newUserDb.values():
            record['updated'] = False

        # member info comes from two sources: members in the clan right
        # now are in the detailed roster; members who are whitelisted to a
        # different clan are on the whitelist. Sadly, the information
        # contained in each is different. It's impossible to find the karma
        # of a user who is away on whitelist, and you can't find the
        # title of a user in the detailed roster.
        members = defaultdict(dict)        
        r1 = ClanWhitelistRequest(self.session)
        d1 = self.tryRequest(r1)
        r2 = ClanDetailedMemberRequest(self.session)
        d2 = self.tryRequest(r2)
        if len(d2['members']) == 0:
            raise RuntimeError("Could not detect any members of clan!")
        
        self.debugLog("{} members on whitelist".format(len(d1['members'])))
        self.debugLog("{} members in clan".format(len(d2['members'])))
        for record in d1['members']:
            uid = int(record['userId'])
            entry = {'userId': uid,
                     'userName': record['userName'],
                     'rank': self._ranks[_rankTransform(record['rankName'])],
                     'whitelist': True,
                     'updated': True}
            self._titles[uid] = record['clanTitle']
            members[uid] = entry
        for record in d2['members']:
            uid = int(record['userId'])
            entry = {'userId': uid,
                     'userName': record['userName'],
                     'rank': self._ranks[_rankTransform(record['rankName'])],
                     'inClan': True,
                     'karma': record['karma'],
                     'updated': True}
            members[uid].update(entry)
            
        self.debugLog("{} members total".format(len(members)))
        
        newMembers = []
        # add some default values and put these in the database
        for uid, record in members.items():
            record.setdefault('karma', 0)
            record.setdefault('inClan', False)
            record.setdefault('whitelist', False)
            record['lastData'] = curTime
            
            key = str(uid)
            if key not in newUserDb:
                newUserDb[key] = {'lastPromotion': self._rolloverTime,
                                  'entryCreated': self._rolloverTime,
                                  'lastActiveCheck': 0}
                newMembers.append(key)
            newUserDb[key].update(record)
                
        # delete old users from database
        deleteAfterSeconds = _daysToSecs(90)
        newUserDb = {k: v for k,v in newUserDb.items()
                        if v.get('lastData') >= curTime - deleteAfterSeconds}
        
        # remove deleted users from _inactiveAstrals
        for k in self._inactiveAstrals.keys():
            if k not in newUserDb:
                del self._inactiveAstrals[k]
            
        if newMembers:
            newMemberList = ["{} (#{}){}".format(
                               record['userName'],
                               record['userId'],
                               "" if record['inClan'] else " [whitelist only]")
                             for key,record in newUserDb.items()
                             if key in newMembers]    
            txt = ("The following users are new clan members:\n\n{}\n"
                   .format("\n".join(newMemberList)))
            self.log("New members: {}".format(", ".join(newMemberList)))
            for uid in self.properties.getAdmins("new_clan_member_notify"):
                self.sendKmail(Kmail(uid, txt))
        
        self._userDb = newUserDb
        self.debugLog("UserDb updated to {} entries".format(len(newUserDb)))
        
    
    # actually run the promotions/demotions
    def _doPromotionDemotion(self, simulate):
        self.log("Running rankings...")
        self._refreshClanMembers()
        for record in self._userDb.values():
            if self._stopNow.is_set():
                return
            if not record.get('updated', False):
                continue
            val = self._determinePromotionDemotion(record['userId'])
            if val == 1:
                self._promote(record['userId'], simulate=simulate)
            elif val == -1:
                self._promote(record['userId'], 
                              isDemotion=True, 
                              simulate=simulate)
        self.log("Done running rankings.")
                
    
    # promote (or demote) a user one rank
    def _promote(self, uid, isDemotion=False, simulate=False):
        # check to make sure user is in a promotable state
        # and get their clan title
        r1 = UserProfileRequest(self.session, uid)
        d1 = self.tryRequest(r1)
        userName = d1['userName']
        userText = "{} (#{})".format(userName, uid)
        if d1['astralSpirit']:
            self._log.warning("Error promoting user {}: is an astral spirit"
                              .format(uid))
            return
        if d1['clanId'] != self.properties.clan:
            self._log.warning("Error promoting user {}: left clan"
                              .format(userText))
            self.debugLog("{}".format(d1))
            return
        isCustomTitle = (d1['clanTitle'] is not None and
                         _rankTransform(d1['clanTitle']) not in self._ranks)
        
        # find correct new rank
        newRankId = None
        newTitle = None
        
        record = self._userDb[str(uid)]
        currentRank = record['rank']
        currentRankId = currentRank['rankId']
        if not isDemotion:
            newRankId = self._promotionRules[currentRankId]['nextRankId']
        else:
            # ranks are singly-linked, so let's find the rank that links
            # to this one
            rankMatch = [rankId for rankId,rule in self._promotionRules.items()
                         if rule['nextRankId'] == currentRank['rankId']]
            if not rankMatch:
                self._log.warning("Could not demote user {}: no rank "
                                  "promotes to {}"
                                  .format(userText, currentRank['rankName']))
                return
            if len(rankMatch) > 1:
                self._log.warning("More than one rank promotes to {1}; "
                                  "user {0} demoted to arbitrary choice"
                                  .format(userText, currentRank['rankName']))
            newRankId = rankMatch[0]
        
        if isCustomTitle:
            newTitle = d1['clanTitle']
        else:
            newTitle = self._promotionRules[newRankId]['rankName']
            
        # currently, there's no way to know if this worked!
        if not simulate:
            r2 = ClanChangeRankRequest(self.session, uid, newTitle, newRankId)
            self.tryRequest(r2)
        self.log("Changed {}'s rank from {} to {}{}"
                 .format(userText, 
                         currentRank['rankName'],
                         self._promotionRules[newRankId]['rankName'],
                         " (simulated)" if simulate else ""))
        if not isDemotion:
            self._userDb[str(uid)]['lastPromotion'] = self._rolloverTime
            
        
    # should a user be promoted, demoted, or neither?
    # return -1 for demotion, 0 for no change, 1 for promotion
    def _determinePromotionDemotion(self, uid):
        key = str(uid)
        record = self._userDb[key]
        userName = record['userName']
        userText = "{} (#{}) [{}]".format(userName, uid, 
                                          record['rank']['rankName'])
        rankId = record['rank']['rankId']
        if rankId not in self._promotionRules:
            self.debugLog("User {}'s rank not in promotion rules."
                          .format(userText))
            return 0
        
        if not record['inClan']:
            # player is whitelisted, there's not much we can do
            self.debugLog("User {} is visiting another clan.".format(userText))
            return 0
        
        karma = record['karma']
        
        rule = self._promotionRules[rankId]
        nextrule = self._promotionRules.get(rule['nextRankId'], {})
        
        # is our karma too low? if so, demote
        if rule['demotionAllowed']:
            if karma < rule['minKarma']:
                self.log("User {} to be demoted ({}/{} karma)."
                         .format(userText, karma, rule['minKarma']))
                return -1
        
        timeSinceLastPromotion = time.time() - record['lastPromotion']
        daysSinceLastPromotion = 1 + _secsToDays(timeSinceLastPromotion)
        
        timeSinceEntryCreated = time.time() - record['entryCreated']
        daysSinceEntryCreated = 1 + _secsToDays(timeSinceEntryCreated)
        
        # are we eligible to be promoted?
        if rule['nextRankId'] is not None:
            if daysSinceLastPromotion >= rule['minDaysBeforePromotion']:            
                if daysSinceEntryCreated >= nextrule.get('minDaysInClan', 0):
                    if karma >= nextrule.get('minKarma', 0):
                        self.log("User {} eligible for promotion!"
                                 .format(userText))
                        self.log("Promotion data: {}; rules {} -> {}"
                                 .format(record, rule, nextrule))
                        return 1
                    else:
                        self.debugLog("User {} does not have enough karma "
                                      "to be promoted (has {}, needs {})."
                                      .format(userText, 
                                              karma, 
                                              nextrule.get('minKarma')))
                else:
                    self.debugLog("User {} has not been in the clan long "
                                  "enough to be promoted ({}/{} days)."
                                  .format(userText,
                                          daysSinceEntryCreated,
                                          nextrule.get('minDaysInClan')))
            else:
                self.debugLog("User {} has not held the current rank long "
                              "enough to be promoted ({}/{} days)."
                              .format(userText,
                                      daysSinceLastPromotion,
                                      rule.get('minDaysBeforePromotion')))
        else:
            self.debugLog("User {} has reached the end of their promotion "
                          "path.".format(userText))

        # stay at the same rank
        return 0


    # perform booting of inactive members
    def _doBooting(self, simulate):
        bootedMembers = []
        if self._daysUntilBoot <= 0:
            return
        self.log("Running bootings...")
        self._refreshClanMembers()
        checkSeconds = _daysToSecs(self._daysUntilBoot)
        curTime = time.time()
        numRecords = len(self._userDb)
        i = 0
        for uid_s, record in self._userDb.items():
            i += 1
            if self._stopNow.is_set():
                break
            if not record.get('updated', False):
                continue
            nextCheckTime = record.get('lastActiveCheck', 0) + checkSeconds
            if curTime >= nextCheckTime:
                prefix = "[{}/{}] ".format(i, numRecords)
                booted = self._bootIfInactive(int(uid_s), simulate, prefix)
                if booted:
                    bootedMembers.append(uid_s)
            else:
                nextCheckDays = 1 + _secsToDays(nextCheckTime - curTime)
                self.debugLog("[{}/{}] Skipping boot check for {}; will "
                              "check in {} days."
                              .format(i, numRecords,
                                      record['userName'], nextCheckDays))
        self.log("Done running bootings.")
        if bootedMembers:
            bootedList = ["{} (#{})".format(record['userName'],
                                            record['userId'])
                          for key,record in self._userDb.items()
                          if key in bootedMembers]    
            txt = ("The following users have been booted and/or "
                   "removed from the clan whitelist:\n\n{}\n"
                   .format("\n".join(bootedList)))
            self.log("Booted members: {}".format(", ".join(bootedList)))
            for uid in self.properties.getAdmins("boot_clan_member_notify"):
                self.sendKmail(Kmail(uid, txt))

        
    # go through the list of inactive astral spirits and visit each player's
    # profile page. If they're not an astral spirit, remove them from the list
    def _updateInactiveAstrals(self):
        self.log("Checking inactive astral spirits...")
        for s_uid in self._inactiveAstrals.keys():
            if self._stopNow.is_set():
                return
            uid = int(s_uid)
            r1 = UserProfileRequest(self.session, uid)
            d1 = self.tryRequest(r1)
            userName = d1['userName']
            if not d1['astralSpirit']:
                del self._inactiveAstrals[s_uid]
                self.log("User {} (#{}) is no longer an astral "
                               "spirit.".format(userName, uid))
            else:
                self.debugLog("User {} (#{}) is still an astral spirit."
                              .format(userName, uid))
        
    
    # check if a user is inactive and boot them if not protected
    # returns True if player was booted
    def _bootIfInactive(self, uid, simulate=False, msgPrefix=""):
        # most inactivity information is available from the user's profile.
        r1 = UserProfileRequest(self.session, uid)
        d1 = self.tryRequest(r1)
        userName = d1['userName']
        
        # add some flags for logging purposes
        flags = []
        record = self._userDb.get(str(uid), {})
        if record.get('inClan', False):
            flags.append("inClan")
        if record.get('whitelist', False):
            flags.append("whitelist")
            
        # userName (#0123456) [flag1/flag2]
        userText = "{} (#{}) [{}]".format(userName, uid, "/".join(flags))
        
        # the one difficult case is if a user is an astral spirit. in this
        # case, their last login is not listed on their page, so we will
        # have to track how long they've been a spirit internally.
        if d1['astralSpirit']:
            # get time since this user was first seen in spirit form
            # and boot them if it's been more than _daysUntilBoot
            t = self._inactiveAstrals.setdefault(str(uid), self._rolloverTime)
            inactiveDays = _secsToDays(self._rolloverTime - t) + 1
            self._log.info("{}User {} has been an astral spirit for the last "
                           "{} days."
                            .format(msgPrefix, userText, inactiveDays))
            if inactiveDays >= self._daysUntilBoot:
                if not self._isInactiveAstralUserSafe(uid):
                    if not simulate:
                        self._boot(uid)
                    self.log("{}Booted user {}{}"
                             .format(msgPrefix, userText, 
                                     " (simulated)" if simulate else ""))
                    return not simulate
                else:
                    self.debugLog("{}User {} protected from booting. Changing "
                                  "last active date to compensate..."
                                  .format(msgPrefix, userText))
                    self._inactiveAstrals[str(uid)] += _daysToSecs(28)
            return False

        # player is NOT an astral spirit, so remove them from the list
        # of "inactive astrals" if they are on that list
        if str(uid) in self._inactiveAstrals:
            del self._inactiveAstrals[str(uid)]

        # now let's take a look at when they last logged in. If it's been
        # more than _daysUntilBoot, boot them! Otherwise, set their
        # lastActiveCheck to a time that will make the bot check them again
        # in a number of days based on how inactive they are.
        # e.g., if I ban after 100 days and a user has been inactive for 40, 
        # check back in around 60 days.
        lastLogin = calendar.timegm(d1['lastLogin'].timetuple())
        daysSinceLastLogin = (self._rolloverTime - lastLogin) - 1
        
        if daysSinceLastLogin > self._daysUntilBoot:
            if not self._isUserSafe(uid):
                if not simulate:
                    self._boot(uid)
                self.log("{}Booted user {}{}"
                         .format(msgPrefix, userText, 
                                 " (simulated)" if simulate else ""))
                return not simulate
            else:
                self.debugLog("{}User {} protected from booting. Changing "
                              "last active date to compensate..."
                              .format(msgPrefix, userText))
                # check again in ~4 weeks
                daysSinceLastLogin = self._daysUntilBoot - 28
        
        # number of days until this person is booted
        margin = max(self._daysUntilBoot - daysSinceLastLogin, 0)
        # add a random amount to this to spread out checking
        nextCheckDays = int(random.uniform(1, 1.1) * margin) + 1
        
        lastCheckSeconds = (self._rolloverTime 
                            + _daysToSecs(nextCheckDays)
                            - _daysToSecs(self._daysUntilBoot))
        self._userDb[str(uid)]['lastActiveCheck'] = lastCheckSeconds
        self.debugLog("{}User {} marked as active (last login {} days "
                      "ago). Checking again in {} days."
                      .format(msgPrefix, userText, 
                              daysSinceLastLogin, nextCheckDays))
        return False


    # boot a member from the clan
    def _boot(self, uid):
        r1 = RemovePlayerFromClanWhitelistRequest(self.session, uid)
        self.tryRequest(r1)
        r2 = BootClanMemberRequest(self.session, uid)
        self.tryRequest(r2)
        if self._bootMessage is not None:
            self.sendKmail(Kmail(uid, self._bootMessage))


    # determine if a user is safe from booting
    def _isUserSafe(self, uid):
        # users are safe for two reasons: either their rank is in _safeRanks
        # or their title is in _safeTitles.
        record = self._userDb[str(uid)]
        
        # check rank (the easy part; it's in the detailed roster)
        if _rankTransform(record['rank']['rankName']) in self._safeRanks:
            return True
        
        # check title; title is listed on whitelist or on the player page
        title = None
        if uid in self._titles:
            # player is on whitelist
            title = self._titles[uid]
        else:
            # load title from player page
            r1 = UserProfileRequest(self.session, uid)
            d1 = self.tryRequest(r1)
            if record['inClan']:
                if 'clanTitle' not in d1:
                    if 'clanId' in d1:
                        return False
                    elif d1['astralSpirit']:
                        return True
                    else:
                        raise RuntimeError("Can't find clan for {}"
                                           .format(uid))
                title = d1['clanTitle']
            else:
                self._log.warning("User {} should be in clan"
                                  .format(uid))
                return True
                
        if title is not None and _rankTransform(title) in self._safeTitles:
            return True
        return False
    
    
    # check if an astral spirit is safe from booting. This is more annoying 
    # than checking a non-spirit because their title isn't on their profile.
    def _isInactiveAstralUserSafe(self, uid):
        record = self._userDb[str(uid)]
        
        # check rank first (easy)
        if _rankTransform(record['rank']['rankName']) in self._safeRanks:
            return True
        
        # check title
        title = None
        if uid in self._titles:
            # player is on whitelist -- we lucked out
            title = self._titles[uid]
        else:
            try:
                # let's cheat a bit: add the user to the whitelist...
                self.log("Temporarily adding player {} (#{}) to whitelist "
                         "(to read title)..."
                         .format(record['userName'], uid))
                normalRank = self._ranks['normalmember']['rankId']
                r1 = AddPlayerToClanWhitelistRequest(self.session, 
                                                     uid, 
                                                     normalRank)
                self.tryRequest(r1)
                # now let's read the whitelist and find their title
                r2 = ClanWhitelistRequest(self.session)
                d2 = self.tryRequest(r2)
                
                matches = [record for record in d2['members'] 
                           if int(record['userId']) == uid]
                if len(matches) != 1:
                    raise RuntimeError("Invalid number of matches for user {}"
                                       .format(uid))
                record = matches[0]
                title = record['clanTitle']
            finally:
                # now let's take them off the whitelist.
                r3 = RemovePlayerFromClanWhitelistRequest(self.session, uid)
                self.tryRequest(r3)
                self.log("Player {} (#{}) removed from whitelist."
                         .format(record['userName'], uid))
        if _rankTransform(title) in self._safeTitles:
            return True
        return False
            
    
    # set everyone's "days in clan" to the minimum for their rank (if they
    # have fewer than that)
    def _raiseDaysInClan(self):
        self._refreshClanMembers()
        curTime = time.time()
        for record in self._userDb.values():
            timeSinceEntryCreated = curTime - record['entryCreated']

            rankId = record['rank']['rankId']
            if rankId in self._promotionRules:
                minDays = self._promotionRules[rankId].get('minDaysInClan', 0)
                minSecs = minDays * 86400
                if timeSinceEntryCreated < minSecs:
                    record['entryCreated'] = self._rolloverTime - minSecs
                    self.log("User {} number of days in clan set to {}"
                             .format(record['userName'], minDays))


    def _eventCallback(self, eData):
        if eData.subject == "raise_days":
            if not self._finishedInit:
                return
            self._raiseDaysInClan()
            return
        if eData.fromName == "sys.system":
            if eData.subject in ["shutdown", 
                                 "manual_restart",
                                 "manual_stop",
                                 "crash"]:
                self._stopNow.set()
                if self._running.is_set():
                    self._log.warning("Detected bot shutdown, aborting...")
            
            
    def _heartbeat(self):
        if self._doFinishInit.is_set():
            self._doFinishInit.clear()
            self._finishInitialization()
        if self._execTime is None:
            return
        if time.time() > self._execTime:
            self._execTime = None
            self._runTasks()
