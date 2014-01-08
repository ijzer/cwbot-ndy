import cwbot.util.DebugThreading as threading
import re
import logging
import urllib2
from unidecode import unidecode
from cwbot import logConfig
from collections import defaultdict
from cwbot.locks import InventoryLock
from cwbot.util.ExceptionThread import ExceptionThread
from cwbot.kolextra.request.SendMessageRequest import SendMessageRequest
from cwbot.kolextra.request.DeleteMessagesRequest import DeleteMessagesRequest
from cwbot.kolextra.request.SaveMessagesRequest import SaveMessagesRequest
from kol.request.StatusRequest import StatusRequest
from kol.request.ItemInformationRequest import ItemInformationRequest
from cwbot.common.exceptions import MessageError
from cwbot.sys.database import encode, decode
from cwbot.util.tryRequest import tryRequest
from cwbot.kolextra.manager.MailboxManager import MailboxManager
from kol.database.ItemDatabase import getItemFromId
from cwbot.kolextra.request.GetDisplayCaseRequest import GetDisplayCaseRequest
from cwbot.kolextra.request.TakeItemsFromDisplayCaseRequest import \
                            TakeItemsFromDisplayCaseRequest 
import kol.Error


def _itemsToDict(itemList, addTo={}):
    """ Convert pyKol-style item list to a dict of (item-id: quantity) pairs.
    """
    newDict = defaultdict(lambda: 0)
    newDict.update(addTo)
    for item in itemList:
        newDict[item['id']] += item['quantity']
    return newDict
        
def _itemsToList(itemDict):
    """ Convert dict of (item-id: quantity) pairs back to pyKol-style list. """
    return [{'id': iid, 'quantity': qty} for iid,qty in itemDict.items()]
    
        
_deferredText = "Here are your items."
_couldNotSendItemsText = ("(I wanted to send you some items, but there was "
                          "an error (are you in Hardcore/Ronin?). "
                          "Send me a kmail with the text "
                          "'cashout' to retrieve your stuff or 'balance' "
                          "to see what I owe you.)")
_outOfStockText = ("(I wanted to send you some items, but I seem to be "
                   "out of stock. I've notified the administrators.")
_extraItemText = "(Extra items attached.)"

_doNotSendItems = set([1649,5668,5674,3054,3624,2307,2313,2306,
                       2312,2305,2311,2308,2314,2304,2310,3274,
                       3275,5539,1995,1996,1997,4333,3280,4530,
                       625,1923])
_withholdItemErrors = [None,
                       kol.Error.ITEM_NOT_FOUND,
                       kol.Error.USER_IN_HARDCORE_RONIN,
                       kol.Error.USER_IS_IGNORING,
                       kol.Error.REQUEST_FATAL]


# Mail Flow Chart:
#
#             MailHandler Thread                          Client Thread
#
#             check kmail
#                  |
#                  |---> Save to DB
#                  |     state=INBOX_DOWNLOADED
#                  |     possibly: notify user that I am in HC/ronin
#                  v
#        delete kmail from server
#                  |                                           
#                  ----> state=INBOX_READY                     
#                                                              
#                                                  client calls getNextKmail()
#                                                               |
#                                     state=INBOX_RESPONDNG <---|
#                                                               v
#                                             handler returns copy of message
#                                                               |
#                                                               |
#                                                               v
#                                                client processes message
#                                                               |
#                                                               |
#                                                               v
#                                             client calls respondToKmail()
#                                                               |
#                                                               |
#                                                               v
#                                            original message deleted from DB
#                                                       save response to DB, 
#                                                       state=OUTBOX_SENDING   
#
#
#  get message w/ state=OUTBOX_SENDING
#                  |
#                  |
#                  v
#     try to send message ---------------------
#        |                                    |
#        |(success)                           |(failure)
#        |                                    |
#        |-> state=OUTBOX_TODELETE            |-> state=OUTBOX_FAILED
#        |                                    | 
#        v                                    v
#    delete message from server         try sending the message without
#        |                              attached items               |
#        |---> state=HANDLED            |                            |
#        v                              |(success)                   |(failure)
#    remove from DB                     |                            |
#                                       |            state=OUTBOX_ <-|
#               state=OUTBOX_WITHHELD <-|              COULDNOTSEND  |
#                                       |                            v
#                                       |                       notify admins
#                                       |                            |
#                                       |                            |
#                                       |                            v
#                                       |                    state=ERROR
#                                       |                  if mail had items:
#                                       |                  make copy with
#                                       |                state=OUTBOX_WITHHELD
#                                       |                            |
#                                       |<----------------------------
#                                       |                             
#                                       v                             
#                      generate "deferred" kmail with items           
#                      add to DB, status=OUTBOX_DEFERRED              
#                      delete old message from DB              
#                                                              
#
#
# NOTE: No cycle detection for sending between bots yet.
#
#
# if the bot undergoes normal shutdown, the only entries in the database
# should be those with states: HANDLED, ERROR, OUTBOX_DEFERRED
#
# If the bot starts up and there entries with other states, here's what
# happens:
#
# INBOX_DOWNLOADED: do nothing, system will try to delete from server again
# INBOX_READY: do nothing, just wait for getNextKmail
# INBOX_RESPONDING: set to INBOX_READY (assume nothing has happened)
# OUTBOX_SENDING: check if the message is in the outbox on server; if so,
#    delete the message from DB, otherwise leave it there so it's sent
# OUTBOX_TODELETE: leave there so it's deleted
# OUTBOX_FAILED: check if a message with same ID is in outbox on server;
#    if so, set status to OUTBOX_WITHHELD, otherwise leave there so it's
#    tried again
# OUTBOX_WITHHELD: leave there so it's set to deferred
# OUTBOX_COULDNOTSEND: leave there, it will be handled.
#

class MailHandler(ExceptionThread):
    INBOX_DOWNLOADED = "I_DOWNLOAD"
    INBOX_READY = "I_READY"
    INBOX_RESPONDING = "I_RESPONDING"
    
    OUTBOX_SENDING = "O_SENDING"
    OUTBOX_FAILED = "O_FAILED"
    OUTBOX_WITHHELD = "O_WITHHOLDING"
    OUTBOX_DEFERRED = "O_DEFERRED"
    OUTBOX_TODELETE = "O_TODELETE"
    OUTBOX_COULDNOTSEND = "O_COULDNOTSEND"
    
    HANDLED = "HANDLED"
    ERROR = "ERROR"
    
    _maxKmailLen = 1700
    _maxTotalKmailLen = _maxKmailLen * 5
    
    
    def __init__(self, session, props, invMan, db):
        self._db = db
        self._receivedMessages = defaultdict(list)
        self._clearedItems = dict((iid, False) for iid in _doNotSendItems)
        logConfig.setFileHandler("mail-handler", 'log/mailhandler.log')
        self._log = logging.getLogger("mail-handler")
        self._log.info("---- Mail Handler startup ----")
        if self._db.version > 1:
            raise Exception("MailHandler cannot use database version {}"
                            .format(self._db.version))
        self._s = session
        self._m = MailboxManager(session)
        self._props = props 
        self._invMan = invMan
        self.__lock = threading.RLock()
        self._event = threading.Event() # set when thread should do something
        self._stopEvent = threading.Event()
        self._name = db.createMailTransactionTable()
        self._initialize()
        self._event.set()
        super(MailHandler, self).__init__(name="MailHandler")


    def canReceiveItems(self):
        r = StatusRequest(self._s)
        d = tryRequest(r, numTries=6, initialDelay=3, scaleFactor=1.25)
        canReceive = ((int(d.get('hardcore',"1")) == 0 and
                      int(d.get('roninleft',"1")) == 0) 
                      or
                      int(d.get('casual',"0")) == 1 
                      or
                      int(d.get('freedralph',"0")) == 1)
        return canReceive


    def notify(self):
        self._event.set()


    def getNextKmail(self):
        """ Get the next Kmail. The state of this kmail is set to RESPONDING.
        You will need to call the respondToKmail() method to set that it has
        been processed, even if you do nothing.
        """
        if not self._online():
            return None
        getItems = self.canReceiveItems()
        con = self._db.getDbConnection(isolation_level="IMMEDIATE")
        try:
            with con:
                c = con.cursor()
                c.execute("SELECT * FROM {} WHERE state=? ORDER BY id ASC "
                          .format(self._name), (self.INBOX_READY,))
                msgAccepted = False
                while not msgAccepted:
                    # loop until we get an "acceptable" message
                    # messages are only unacceptable if they have items while
                    # we are in HC/Ronin
                    msg = c.fetchone()
                    if msg is None:
                        return None # no new messages
                    if getItems:
                        msgAccepted = True # accept all messages
                    else:
                        message = decode(msg['data'])
                        # message accepted only if it does not have items
                        msgAccepted = not message.get('items', {})
                            
                c.execute("UPDATE {} SET state=? WHERE id=?"
                          .format(self._name),
                          (self.INBOX_RESPONDING, msg['id']))
                message = decode(msg['data'])
                self._log.debug("Kmail ready -> responding: {}"
                                .format(msg['id']))
                return message
        finally:
            con.close()

           
    def respondToKmail(self, kmailId, responses=[]):
        """ State that you have responded to a kmail. If you supply responses
        here, they will be sent. This is the correct function to use to ensure
        proper response in case of a power failure.
        """
        with self.__lock:
            if responses:
                for response in responses:
                    self._checkItems(response)
            con = self._db.getDbConnection(isolation_level="IMMEDIATE")
            try:
                with con:
                    c = con.cursor()
                    c.execute("SELECT * FROM {} WHERE kmailId=? AND state=?"
                              .format(self._name),
                              (kmailId, self.INBOX_RESPONDING))
                    row = c.fetchone()
                    id_ = None
                    if row is not None:
                        id_ = row['id']
                    # remove the inbox kmail (status=INBOX_RESPONDING)
                    c.execute("DELETE FROM {} WHERE kmailId=? AND state=?"
                              .format(self._name),
                              (kmailId, self.INBOX_RESPONDING))
                    if c.rowcount == 0:
                        raise IndexError("No such kmail with id {}"
                                         .format(kmailId))
                    if not responses:
                        self._log.debug("Silently processed kmail {}"
                                        .format(id_))
                        return
                    
                    # insert replies into database (status=OUTBOX_SENDING)
                    self._log.debug("Kmail {} processed. Adding responses:"
                                    .format(id_))
                    for response in responses:
                        deferMode = response.get('defer', False)
                        insertState = (self.OUTBOX_SENDING if not deferMode
                                       else self.OUTBOX_WITHHELD) 
                        self._insertSplitKmail(c, insertState, 
                                               response, reserveItems=True)
                self._event.set()
            finally:
                con.close()


    def sendNonresponseKmail(self, message):
        """ Send a Kmail that is NOT a response to a received kmail. """
        with self.__lock:
            self._checkItems(message)
            con = self._db.getDbConnection(isolation_level="IMMEDIATE")
            try:
                with con:
                    c = con.cursor()
                    self._log.debug("Sending new kmail...")
                    self._insertSplitKmail(c, self.OUTBOX_SENDING, message,
                                           reserveItems=True)
                self._event.set()
            finally:
                con.close()

    
    def sendDeferredItems(self, uid):
        """ Send deferred kmail items+meat to user."""
        con = self._db.getDbConnection()
        try:
            c = con.cursor()
            with con:
                c.execute("SELECT * FROM {} WHERE state=? AND userId=? "
                          "ORDER BY id ASC LIMIT 2"
                          .format(self._name), (self.OUTBOX_DEFERRED, uid))
                rows = c.fetchall()
                if len(rows) == 0:
                    raise IndexError("No deferred kmails for user {}"
                                     .format(uid))
                elif len(rows) > 1:
                    raise Exception("Multiple deferred kmails detected for "
                                    "user {}".format(uid))
                msg = rows[0]
                message = decode(msg['data'])
                mid = msg['id']
                self._log.info("Sending deferred kmail to user {}"
                               .format(uid))
                
                # unreserve items from inventory
                self._invMan.clearReservationsWtihDbCursor(
                    self._name, mid, c)
                # send new kmail
                self._insertSplitKmail(c, self.OUTBOX_SENDING, message, 
                                       reserveItems=True)
                c.execute("DELETE FROM {} WHERE id=?".format(self._name),
                          (mid,))
                self._event.set()
        finally:
            con.close()        
        
        
    def getDeferredItems(self, uid):
        """ Send deferred kmail items+meat to user. Items are pulled out
        of the closet. """
        con = self._db.getDbConnection()
        try:
            c = con.cursor()
            with con:
                c.execute("SELECT * FROM {} WHERE state=? AND userId=? "
                          "ORDER BY id ASC LIMIT 2"
                          .format(self._name), (self.OUTBOX_DEFERRED, uid))
                rows = c.fetchall()
                if len(rows) == 0:
                    return (0, {})
                elif len(rows) > 1:
                    raise Exception("Multiple deferred kmails detected for "
                                    "user {}".format(uid))
                message = decode(rows[0]['data'])
                return (message['meat'], _itemsToDict(message['items']))
        finally:
            con.close()        

            
    def _insertSplitKmail(self, cursor, state, message, reserveItems):
        """ This function adds a new (pending) outgoing kmail to the database
        and splits it so that the wordcount/itemcount is within KoL limits.
        
        This function takes a cursor as an argument and does NOT commit after
        its actions.
        
        ALL messages should be ultimately sent using this function, so that
        items are accounted and reserved properly.
        """
        insertions = []
        truncateMsg = " (message truncated)"
        self._log.debug("Splitting outgoing kmail {}".format(message))
        uid = message['userId']
        text = message['text']
        items = _itemsToDict(message.get('items', []))
        meat = message.get('meat', 0)
        if len(text) > self._maxTotalKmailLen:
            oldText = text
            text = text[:self._maxTotalKmailLen - len(truncateMsg)] 
            text += truncateMsg
            self._log.debug("Truncated message text '{}' to '{}'"
                            .format(oldText, text))
        
        # split text into multiple kmails
        messageWords = re.split(r'(\s+)', text)
        textList = [""]
        for word in messageWords:
            if len(word) > 1000:
                word = word[:1000] + "..."
            if len(textList[-1]) + len(word) <= self._maxKmailLen:
                textList[-1] += word
            else:
                if re.search(r'\S', word) is not None:
                    textList[-1] += " ..."
                    textList.append(word)
                    
        # split items into multiple kmails
        itemList = [{}]
        for iid,qty in items.items():
            if len(itemList[-1]) < 11:
                itemList[-1][iid] = qty
            else:
                itemList.append({iid:qty})
        mailItemList = map(_itemsToList, itemList)

        mails = [{'userId': uid, 'text': txt, 'meat': 0, 'items': []}
                 for txt in textList]
        itemMails = []
        for idx,d in enumerate(mailItemList):
            if idx == 0:
                mails[-1]['meat'] = meat
                mails[-1]['items'] = d
            else:
                itemMails.append({'userId': uid, 'text': _extraItemText, 
                                  'meat': 0, 'items': d}) 
             
        allMails = [(m, False) for m in mails]
        allMails.extend([(m, True) for m in itemMails])
        # send mails in REVERSE ORDER -- that way they show up "correctly"
        for mail, isItemMail in reversed(allMails):
            if isItemMail:
                cursor.execute("INSERT INTO {}(state, userId, data, itemsOnly)"
                               " VALUES(?,?,?,1)".format(self._name),
                               (state, uid, encode(mail)))
            else:
                cursor.execute("INSERT INTO {}(state, userId, data) "
                               "VALUES(?,?,?)".format(self._name),
                               (state, uid, encode(mail)))
            mailId = cursor.lastrowid
            insertions.append(mailId)
            if reserveItems:
                self._invMan.reserveItemsWithDbCursor(
                    _itemsToDict(mail['items']), self._name, mailId, cursor)
        
        self._log.debug("Inserted the following mails: {}"
                        .format(', '.join(str(i) for i in insertions)))
        

    def _getEncodedId(self, message):
        txt = message.get('text', "")
        matches = re.findall(r'\(mail-[Ii]d: (\d+)\)', txt, re.MULTILINE)
        if not matches:
            return None
#            raise Exception("Invalid sent Kmail: {}. If this message was "
#                            "manually sent, please delete it from the outbox."
#                            .format(message))
        return int(matches[-1])


    def _initialize(self):
        con = self._db.getDbConnection()
        try:
            c = con.cursor()
            
            # get all previously sent messages
            outMsgs = self._m.getAllMessages(box="Outbox", 
                                             allowUnknownItems=True)
            outMsgIds = []
                # find if any messages needed to be sent or failed
            c.execute("SELECT * FROM {} WHERE state in (?,?) LIMIT 1"
                      .format(self._name),
                      (self.OUTBOX_FAILED,self.OUTBOX_SENDING))
            if c.fetchone() is not None:
                # get list of all successfully sent messages
                outMsgIdList = [self._getEncodedId(m) for m in outMsgs]
                outMsgIds = set(o for o in outMsgIdList if o is not None)

            # delete all handled mail (from yesterday)
            with con:
                c.execute("DELETE FROM {} WHERE state=?".format(self._name),
                          (self.HANDLED,))
                n = c.rowcount
                if n > 0:
                    self._log.debug("Removed {} handled kmails from database."
                                    .format(n))
            
            # not processed: change to INBOX_READY
            with con:
                c.execute("UPDATE {} SET state=? WHERE state=?"
                          .format(self._name), (self.INBOX_READY, 
                                                self.INBOX_RESPONDING))
                n = c.rowcount
                if n > 0:
                    self._log.debug("Changed {} unprocessed kmails from "
                                    "RESPONDING to READY.".format(n))
                
            # delete outgoing mail from DB if already sent
            with con:
                c.execute("SELECT * FROM {} WHERE state=?".format(self._name),
                          (self.OUTBOX_SENDING,))
                for msg in c.fetchall():
                    if msg['id'] in outMsgIds:
                        # this message was successfully sent
                        self._log.debug("Setting sent kmail {} to TODELETE"
                                        .format(msg['id']))
                        c.execute("UPDATE {} SET state=? WHERE id=?"
                                  .format(self._name), 
                                  (self.OUTBOX_TODELETE, msg['id']))
            
            # if an ougoing message failed but something was sent, change
            # its status to withheld
            with con:
                c.execute("SELECT * FROM {} WHERE state=?".format(self._name),
                          (self.OUTBOX_FAILED,))
                for msg in c.fetchall():
                    if msg['id'] in outMsgIds:
                        # this message was successfully sent
                        self._log.debug("Setting sent kmail {} to WITHHELD"
                                        .format(msg['id']))
                        c.execute("UPDATE {} SET state=? WHERE id=?"
                                  .format(self._name), 
                                  (self.OUTBOX_WITHHELD, msg['id']))

            # outbox messages are now unneeded
            self._log.info("Deleting {} old messages from outbox..."
                           .format(len(outMsgs)))
            for message in outMsgs:
                mid = self._getEncodedId(message)
                if mid is not None:
                    self._log.info("Deleting message {}...".format(mid))
                else:
                    self._log.info("Deleting unmarked message...")                
                self._deleteKmail(message, box="Outbox")

            self._send(con)
            self._receive(con)
            self._send(con)
        finally:
            con.close()
            
            
    def _checkStock(self):
        with InventoryLock.lock:
            self._invMan.refreshInventory()
            inv = self._invMan.completeInventory()
            r = StatusRequest(self._s)
            d = tryRequest(r, numTries=6, initialDelay=3, scaleFactor=1.25)
            meat = int(d['meat'])
            itemsOwed = {}
            meatOwed = 0
            
            con = self._db.getDbConnection()
            c = con.cursor()
            c.execute("SELECT * FROM {}".format(self._name))
            msg = c.fetchone()
            while msg is not None:
                if msg['state'] in [self.OUTBOX_SENDING,
                                    self.OUTBOX_DEFERRED]:
                    message = decode(msg['data'])
                    itemsOwed = _itemsToDict(message.get('items', []), 
                                             itemsOwed)
                    meatOwed += message.get('meat', 0)
                msg = c.fetchone()
            difference = dict((iid, inv.get(iid, 0) - qty)
                              for iid,qty in itemsOwed.items())
            deficit = dict((iid, -diff) for iid,diff in difference.items()
                           if diff < 0)
            if deficit:
                # get items in display case
                r2 = GetDisplayCaseRequest(self._s)
                d2 = tryRequest(r2)
                display = _itemsToDict(d2['items'])
                difference = dict(
                    (iid, inv.get(iid, 0) + display.get(iid, 0) - qty)
                    for iid,qty in itemsOwed.items())
                deficit = dict((iid, -diff) for iid,diff in difference.items()
                               if diff < 0)
            if deficit or meatOwed > meat:
                # notify admins of item deficit!
                warningText = ("Warning: {} has an item deficit of: \n"
                               .format(self._props.userName))
                for iid, d in deficit.items():
                    warningText += ("\n{}: {}"
                                    .format(
                                        d, getItemFromId(iid).get(
                                            'name', "item ID {}".format(iid))))
                if meatOwed > meat:
                    warningText += "\n{} meat".format(meatOwed-meat)
                with con:
                    c2 = con.cursor()
                    for adminUid in self._props.getAdmins("mail_fail"):
                        # notify admins of deficit
                        
                        newMsg = {'userId': adminUid, 'meat': 0,
                                  'text': warningText, 'items': []}
                        self._insertSplitKmail(c2, self.OUTBOX_SENDING, 
                                               newMsg, reserveItems=False)
        

    def stop(self):
        self._stopEvent.set()
        self._event.set()
    
    
    def _run(self):
        firstRun = True
        while self._online() and not self._stopEvent.is_set():
            newMail = self._event.wait(10)
            con = self._db.getDbConnection()
            try:
                self._send(con)
                if newMail:
                    self._event.clear()
                    self._receive(con)
                    self._send(con)
            finally:
                con.close()
            if firstRun:
                firstRun = False
                self._checkStock()
        con = self._db.getDbConnection()
        try:
            self._log.info("Finishing mail tasks...")
            con = self._db.getDbConnection()
            self._send(con)
            self._send(con)
        finally:
            con.close()
            self._log.info("---- Mail Handler shutdown ----\n")
        
    
    def _online(self):
        try:
            tryRequest(StatusRequest(self._s), nothrow=False, numTries=6,
                       initialDelay=10, scaleFactor=1)
            return True
        except (kol.Error.Error, urllib2.HTTPError):
            pass
        return False
        

    def _sendKmail(self, idCode, message, sendItemWarning=False):
        # append idCode to bottom: \n\n(mail-id: NUMBER)
        message['text'] += "\n\n"
        if sendItemWarning:
            if message.get('out_of_stock', False):
                message['text'] += _outOfStockText + "\n"
            else:
                message['text'] += _couldNotSendItemsText + "\n"
        message['text'] += "(mail-id: {})".format(idCode)
        
        # remove any unicode characters
        message['text'] = unidecode(message['text'])
        with InventoryLock.lock:
            self._invMan.refreshInventory()
            inv = self._invMan.completeInventory()
            items = _itemsToDict(message.get('items', []))
            for iid,qty in items.items():
                inInventory = inv.get(iid, 0)
                if inInventory < qty:
                    self._log.info("Short on item {}; taking from DC..."
                                   .format(iid))
                    r = TakeItemsFromDisplayCaseRequest(
                        self._s, [{'id': iid, 'quantity': qty - inInventory}])
                    tryRequest(r)
            self._invMan.refreshInventory()
            inv = self._invMan.completeInventory()

            # check for items in stock, and if they are sendable
            filteredItems = {}
            for iid,qty in items.items():
                inInventory = inv.get(iid, 0)
                if inInventory < qty:
                    message['out_of_stock'] = True
                if inInventory > 0:
                    if iid not in self._clearedItems:
                        r = ItemInformationRequest(self._s, iid)
                        d = tryRequest(r)['item']
                        approved = d.get('canTransfer', False)
                        self._clearedItems[iid] = approved
                        self._log.debug("Item {} {} for kmail"
                                        .format(iid, "APPROVED" if approved
                                                     else "REJECTED"))
                    if self._clearedItems[iid]:
                        filteredItems[iid] = qty
                    else:
                        self._log.info("Item {} rejected from kmail."
                                       .format(iid))
                else:
                    filteredItems[iid] = qty
            message['items'] = _itemsToList(filteredItems)

            r = SendMessageRequest(self._s, message)
            # we can't try this more than once! if there's some sort of 
            # error, it will send multiple times.
            tryRequest(r, numTries=1)

        
    def _deleteKmail(self, message, **kwargs):
        r = DeleteMessagesRequest(self._s, [message['id']], **kwargs)
        try:
            result = tryRequest(r)
            self._log.info("Deleted message.".format(result))
        except MessageError:
            pass


    def _saveKmail(self, message, **kwargs):
        r = SaveMessagesRequest(self._s, [message['id']], **kwargs)
        try:
            result = tryRequest(r)
            self._log.info("Saved message {}".format(result))
        except Exception:
            self._log.info("Could not save {}. Gave up.".format(message))
            
                    
    def _receive(self, con):
        if self._online():
            self._downloadNewKmails(con)
        if self._online():
            self._deleteDownloadedKmails(con)
            
    
    def _downloadNewKmails(self, con):
        getItems = self.canReceiveItems()
        with con:
            c = con.cursor()
            messages = self._m.getAllMessages("Inbox", True, True)
            for message in messages:
                # delete the date, it's not JSON serializable
                del message['date']
                
                c.execute("INSERT INTO {0}(kmailId, state, userId, data) "
                          "SELECT ?,?,?,? "
                          "WHERE NOT EXISTS (SELECT 1 FROM {0} "
                                            "WHERE kmailId=?)"
                          .format(self._name), 
                          (message['id'], self.INBOX_DOWNLOADED, 
                          message['userId'], encode(message), message['id']))
                mid = c.lastrowid
                self._log.info("Downloaded new message {}: {}"
                               .format(mid, message))
                if not getItems:
                    if message.get('items', {}):
                        # send warning!
                        self._insertSplitKmail(
                                c, self.OUTBOX_SENDING, 
                                {'userId': message['userId'],
                                 'text': ("NOTICE: I am currently in Hardcore "
                                         "or Ronin and can't access the items "
                                         "you sent me. Your mail will be "
                                         "processed when I am able to open "
                                         "it.")}, 
                                reserveItems=False)
                        self._log.info("Unable to respond to message {} due "
                                       "to Ronin/HC".format(mid))

        
    def _deleteDownloadedKmails(self, con):
        c = con.cursor()
        c.execute("SELECT * FROM {} WHERE state=?".format(self._name),
                  (self.INBOX_DOWNLOADED,))
        for msg in c.fetchall():
            self._deleteKmail(decode(msg['data']))
            with con:
                c2 = con.cursor()
                c2.execute("UPDATE {} SET state=? WHERE id=?"
                           .format(self._name),
                           (self.INBOX_READY, msg['id']))
            
            
    def _send(self, con):
        if self._online():
            self._handleSending(con)
        if self._online():
            self._handleToDelete(con)
        if self._online():
            self._handleFailed(con)
        if self._online():
            self._handleWithheld(con)
        if self._online():
            self._handleCouldNotSend(con)


    def _handleSending(self, con):
        c = con.cursor()
        c.execute("SELECT * FROM {} WHERE state=? ORDER BY id ASC"
                  .format(self._name),
                  (self.OUTBOX_SENDING,))
        for msg in c.fetchall():
            message = decode(msg['data'])
            self._log.debug("Sending message {}: {}".format(msg['id'],
                                                            message))
            if not self._online():
                return
            success = False
            exc = None
            try:
                self._sendKmail(msg['id'], message)
                success = True
            except kol.Error.Error as e:
                if not self._online():
                    return
                exc = e
            
            if success:
                with con:
                    c2 = con.cursor()
                    c2.execute("UPDATE {} SET state=? WHERE id=?"
                               .format(self._name),
                               (self.OUTBOX_TODELETE, msg['id']))
                    self._log.info("Message {} sent.".format(msg['id']))
            else:
                with con:
                    c2 = con.cursor()
                    if msg['itemsOnly'] != 1:
                        if (not message['items']) and message['meat'] == 0:
                            # message failed, do not resend
                            c2.execute(
                                "UPDATE {} SET state=?, error=? WHERE id=?"
                                .format(self._name), (self.OUTBOX_COULDNOTSEND, 
                                                      exc.code, msg['id']))
                            self._log.info("Failed to send message {}: {}. "
                                           "State set to OUTBOX_COULDNOTSEND."
                                           .format(msg['id'], exc))
                        else:
                            # try sending without any items
                            c2.execute(
                                "UPDATE {} SET state=?, error=? WHERE id=?"
                                .format(self._name), 
                                (self.OUTBOX_FAILED, exc.code, msg['id']))
                            self._log.debug("Failed to send message {}: {}. "
                                            "State set to OUTBOX_FAILED."
                                            .format(msg['id'], exc))
                    else:
                        # just add to withheld list (do not send failure msg)
                        # NOTE: itemsOnly is set to 1 for a message
                        # continuation. This way, users will only receive
                        # once "message failed to send" kmail.
                        c2.execute("UPDATE {} SET state=?, error=? WHERE id=?"
                                   .format(self._name),
                                   (self.OUTBOX_WITHHELD, exc.code, msg['id']))
                        

    def _handleToDelete(self, con):
        c = con.cursor()
        c.execute("SELECT * FROM {} WHERE state=?".format(self._name),
                  (self.OUTBOX_TODELETE,))
        for msg in c.fetchall():
            mid = msg['id']
            if not self._online():
                return
            with con:
                c2 = con.cursor()
                c2.execute("UPDATE {} SET state=? WHERE id=?"
                           .format(self._name), (self.HANDLED, mid))

                # release items from database
                self._invMan.clearReservationsWtihDbCursor(
                    self._name, mid, c2)
                self._log.debug("Deleting message {} from outbox on next "
                                "boot. State set to HANDLED.".format(mid))

        
    def _handleFailed(self, con):
        c = con.cursor()
        c.execute("SELECT * FROM {} WHERE state=?".format(self._name),
                  (self.OUTBOX_FAILED,))
        for msg in c.fetchall():
            if not self._online():
                return
            
            # strip items and meat
            message = decode(msg['data'])
            message['items'] = []
            message['meat'] = 0
            success = False
            exc = None
            try:
                # try resending without items/meat
                if message != decode(msg['data']):
                    self._sendKmail(msg['id'], message, 
                                    sendItemWarning=True)
                    success = True
                    self._log.debug("Sent item retention warning for message "
                                    "{}.".format(msg['id']))
                else:
                    self._log.debug("Message {} has no items; skipping "
                                    "retention.".format(msg['id']))

            except kol.Error.Error as e:
                if not self._online():
                    # no point sending, we got logged out!
                    return
                self._log.debug("Error sending retention message for kmail {}."
                                .format(msg['id']))
                exc = e
                
                
            if success:
                with con:
                    # set to withheld state
                    c2 = con.cursor()
                    c2.execute("UPDATE {} SET state=?, error=? WHERE id=?"
                               .format(self._name),
                               (self.OUTBOX_WITHHELD, None, msg['id']))
                    self._log.info("Kmail {} state set to OUTBOX_WITHHELD"
                                   .format(msg['id']))
            else:
                with con:
                    # set to could not send state
                    code = exc.code if exc is not None else msg['error']
                    c2 = con.cursor()
                    c2.execute("UPDATE {} SET state=?, error=? WHERE id=?"
                               .format(self._name),
                               (self.OUTBOX_COULDNOTSEND, code, msg['id']))
                    self._log.info("Kmail {} state set to OUTBOX_COULDNOTSEND "
                                   "due to error {}".format(msg['id'], exc))
            
            
    def _handleWithheld(self, con):
        c = con.cursor()
        c.execute("SELECT * FROM {} WHERE state=?".format(self._name),
                  (self.OUTBOX_WITHHELD,))
        for msg in c.fetchall():
            if not self._online():
                return
            # kmail was withheld. We need to create a "deferred" kmail
            # with the items.
            uid = msg['userId']
            message = decode(msg['data'])
            mid = msg['id']
            if message.get('meat', 0) == 0:
                if len(message.get('items', [])) == 0:
                    continue
            c2 = con.cursor()
            # find if there is already a deferred message with items/meat
            c2.execute("SELECT * FROM {} WHERE state=? AND userId=? "
                       "ORDER BY id ASC LIMIT 2"
                       .format(self._name), 
                       (self.OUTBOX_DEFERRED, uid))
            rows = c2.fetchall()
            if len(rows) == 0:
                # set to deferred
                message['text'] = _deferredText
                with con:
                    c2.execute("UPDATE {} SET data=?, state=? WHERE id=?"
                               .format(self._name),
                               (encode(message), self.OUTBOX_DEFERRED, mid))
                    self._log.info("Retained items for message {} from "
                                   "outbox. State set to DEFERRED."
                                   .format(msg['id']))

            elif len(rows) == 1:
                # merge items with old deferred message
                message2 = decode(rows[0]['data'])
                mid2 = rows[0]['id']
                itemQtyDict = _itemsToDict(message['items'])
                itemQtyDictMerge = _itemsToDict(message2['items'], itemQtyDict)
                message2['items'] = _itemsToList(itemQtyDictMerge)
                # merge meat
                message2['meat'] += message['meat']
                with con:
                    c2.execute("UPDATE {} SET data=? WHERE id=?"
                               .format(self._name),
                               (encode(message2), mid2))
                    c2.execute("DELETE FROM {} WHERE id=?".format(self._name),
                               (mid,))
                    self._log.info("Retained items for message {} from "
                                   "outbox (merged). State set to DEFERRED."
                                   .format(mid))
                    
                    # merge item reservations
                    self._invMan.clearReservationsWtihDbCursor(
                        self._name, mid, c2)
                    self._invMan.clearReservationsWtihDbCursor(
                        self._name, mid2, c2)
                    self._invMan.reserveItemsWithDbCursor(
                        itemQtyDictMerge, self._name, mid2, c2)
                    
            else:
                raise Exception("Found more than one deferred kmail: "
                                "{}".format(', '.join(decode(msg['data']))
                                            for msg in rows))
                        
                        
    def _handleCouldNotSend(self, con):
        c = con.cursor()
        c.execute("SELECT * FROM {} WHERE state=?".format(self._name),
                  (self.OUTBOX_COULDNOTSEND,))
        for msg in c.fetchall():
            if not self._online():
                return
            message = decode(msg['data'])
            uid = msg['userId']
            mid = msg['id']
            with con:
                c2 = con.cursor()
                self._log.info("Mail could not send: {}. "
                               "Notifying admins..."
                               .format(mid))
                if "mail_fail" not in self._props.getPermissions(uid):
                    for adminUid in self._props.getAdmins("mail_fail"):
                        # notify admins of failure
                        newMsg = {'userId': adminUid, 
                                  'text': "NOTICE: The following kmail "
                                          "failed to send: {}"
                                          .format(message),
                                  'meat': 0, 'items': []}
                        self._insertSplitKmail(c2, self.OUTBOX_SENDING, 
                                               newMsg, reserveItems=False)
                else:
                    self._log.error("Error dispatching notification to "
                                    "administrator: {}".format(message))
                    
                # mark as withheld if any items are there
                newState = self.ERROR
                errorCode = msg['error']
                newError = None
                if message['items']:
                    newState = self.OUTBOX_WITHHELD
                    if errorCode not in _withholdItemErrors:
                        # unreserve items. There's no use holding on to them; 
                        # we will never be able to recover. It's probably an
                        # invalid user ID anyway.
                        newState = self.HANDLED
                        newError = errorCode
                        self._invMan.clearReservationsWtihDbCursor(
                                                    self._name, mid, c2)
                        self._log.warning("Error trying to send kmail {}; "
                                          "giving up and releasing items."
                                          .format(message))
                    # also copy message as ERROR
                    c2.execute("INSERT INTO {0}"
                                    "(state, userId, data, error, kmailId) "
                               "SELECT ?, userId, data, error, id FROM {0} "
                               "WHERE id=?".format(self._name),
                               (self.ERROR, mid))
                c2.execute(
                    "UPDATE {} SET state=?, error=? WHERE id=?"
                    .format(self._name), (newState, newError, mid))
                        
        
    def _checkItems(self, message):
        items = _itemsToDict(message['items'])
        with InventoryLock.lock:
            self._invMan.refreshInventory()
            inv = self._invMan.inventory()
            r = GetDisplayCaseRequest(self._s)
            d = tryRequest(r)
            inv = _itemsToDict(d['items'], inv)
            for iid,qty in items.items():
                if inv.get(iid, 0) < qty:
                    raise MessageError("Not enough of item {} in inventory."
                                       .format(iid)) 
                
        
