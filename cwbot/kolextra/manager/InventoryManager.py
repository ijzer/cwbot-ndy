import copy

from cwbot.locks import InventoryLock
from kol.request.InventoryRequest import InventoryRequest
from cwbot.util.tryRequest import tryRequest


class InventoryManager(object):
    """This class manages a user's inventory.
    It is heavily modified from pyKol to also use the global DB and allow
    "reservation" of items, that are not reflected in inventory until released.
    This is mostly for compatibility with the mailHandler.
    
    Reserved items are held in inventory (as opposed to the closet or the DC).
    """
    __lock = InventoryLock.lock
    
    def __init__(self, session, db):
        "Initializes the InventoryManager with a particular KoL session."
        with self.__lock:
            self.session = session
            self.__items = {}
            self._db = db
            self._name = self._db.createInventoryReservationTable()
            session.inventoryManager = self
            self.refreshInventory()
            self.reserveItems({}, "a", "b") # check DB integrity

    def refreshInventory(self):
        """ Refresh the inventory list. """
        with self.__lock:
            self.__items = {}
            r = InventoryRequest(self.session)
            data = tryRequest(r)
            for item in data["items"]:
                self.__items[item["id"]] = item["quantity"]
            
    def inventory(self):
        """ Get a map of (item-id, quantity) pairs that represents the bot's
        inventory. Reserved items are NOT INCLUDED in this total! """
        with self.__lock:
            itemCopy = copy.deepcopy(self.__items)
            con = self._db.getDbConnection(isolation_level="IMMEDIATE")
            try:
                c = con.cursor()
                c.execute("SELECT * FROM {}".format(self._name))
                for row in c.fetchall():
                    iid = row['iid']
                    qty = row['reserved']
                    inInventory = itemCopy.get(iid, 0)
                    itemCopy[iid] = inInventory - qty
                    if inInventory == qty:
                        del itemCopy[iid]
            finally:
                con.close()
            return itemCopy

    def completeInventory(self):
        """ Works like .inventory(), but includes reserved items. """
        with self.__lock:
            itemCopy = copy.deepcopy(self.__items)
            return itemCopy

    def reserveItem(self, iid, qty, reserveName, reserveInfo):
        """ Reserve a single item. """
        self.reserveItems({iid: qty}, reserveName, reserveInfo)

    def releaseItem(self, iid, qty, reserveName, reserveInfo):
        """ Release a single item (i.e., reserve a negative number). """
        self.reserveItems({iid: -qty}, reserveName, reserveInfo)
        
    def releaseItems(self, iidQtyDict, reserveName, reserveInfo):
        """ Release multiple items (i.e., negative numbers of items). """
        self.reserveItems(dict((iid, -qty) for iid,qty in iidQtyDict.items()),
                          reserveName, reserveInfo)
            
    def reserveItems(self, iidQtyDict, reserveName, reserveInfo):
        """ Reserve items with the InventoryManager. iidQtyDict should
        be a dict of (item-id, quantity) pairs that specifies the number of
        each item to reserve; negative quantities indicates that the specified
        number of items should be released (un-reserved). reserveName is
        a name that indicates what system is responsible for the reservation,
        and reserveInfo is an integer that can be used to group reservations.
        """
        with self.__lock:
            con = self._db.getDbConnection(isolation_level="IMMEDIATE")
            try:
                with con:
                    c = con.cursor()
                    self.reserveItemsWithDbCursor(iidQtyDict, reserveName, 
                                                  reserveInfo, c)
            finally:
                    con.close()


    def reserved(self, reserveName=None, reserveInfo=None):
        """ Get a dictionary of reserved items. If reserveName is specified,
        this returns only the items reserved with that reserveName. If
        reserveInfo is specified, only the items reserved with that
        reserveInfo value are returned. If both are specified, the
        reservations are filtered by both criteria. """
        with self.__lock:
            con = self._db.getDbConnection(isolation_level="IMMEDIATE")
            try:
                with con:
                    c = con.cursor()
                    if reserveName is None and reserveInfo is None:
                        c.execute("SELECT iid,sum(reserved) AS reservations"
                                  "FROM {} GROUP BY iid"
                                  .format(self._names))
                    elif reserveName is None:
                        c.execute("SELECT iid,sum(reserved) AS reservations"
                                  "FROM {} WHERE reserveInfo=? GROUP BY iid"
                                  .format(self._names), (reserveInfo,))
                    elif reserveInfo is None:
                        c.execute("SELECT iid,sum(reserved) AS reservations"
                                  "FROM {} WHERE reservedBy=? GROUP BY iid"
                                  .format(self._names), (reserveName,))
                    else:
                        c.execute("SELECT iid,sum(reserved) AS reservations"
                                  "FROM {} "
                                  "WHERE reservedBy=? AND reserveInfo=? "
                                  "GROUP BY iid"
                                  .format(self._names), 
                                  (reserveName, reserveInfo))
                        
                    return dict((row['iid'], row['reservations']) 
                                for row in c.fetchall())
            finally:
                con.close()


    def reserveItemsWithDbCursor(self, iidQtyDict, reserveName, 
                                 reserveInfo, cursor):
        """ Manually reserve items using a sqlite3 database cursor. Do not
        commit to database after execution. 
        This function groups reservations by iid and reserveName and 
        reserveInfo. That is, if the same item is reserved twice, the total
        quantity will only be combined if reserveName and reserveInfo match.
        Otherwise, a new row will be added to the database. """
        for iid,qty in iidQtyDict.items():
            cursor.execute("UPDATE {} SET reserved = reserved + ? "
                           "WHERE iid=? AND reservedBy=? AND reserveInfo=?"
                           .format(self._name), (qty,iid,reserveName, 
                                                 reserveInfo))
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO "
                               "{}(iid,reserved,reservedBy,reserveInfo) "
                               "VALUES(?,?,?,?)"
                               .format(self._name), (iid,qty,reserveName,
                                                     reserveInfo))
        cursor.execute("DELETE FROM {} WHERE reserved=0"
                  .format(self._name))
        cursor.execute("SELECT * FROM {} WHERE reserved < 0 LIMIT 1"
                  .format(self._name))
        badRequest = cursor.fetchone()
        if badRequest is not None:
            iid = badRequest['id']
            qtyRequested = iidQtyDict.get(iid, 0)
            reservedAlready = badRequest['reserved'] + qtyRequested 
            if reservedAlready >= 0 and qtyRequested > 0:
                raise ValueError("Can't release {} of item {} "
                                 "because only {} are reserved by {}:{}"
                                 .format(qtyRequested, iid,
                                         reservedAlready, reserveName,
                                         reserveInfo))
            else:
                raise Exception("FATAL ERROR: "
                                "Inventory database in invalid "
                                "state: negative reservation of "
                                "item {}".format(iid))
                
    def clearReservationsWtihDbCursor(self, reserveName, reserveInfo,
                                      cursor):
        """ Clear all items with the specified reserveName and/or reserveInfo.
        If both reserveName and reserveInfo are specified, this clears all
        reservations that match. If one of the two is None, then it clears all
        reservations that match the other argument. For example, to clear all
        reservations with the reserveName "test", set reserveName="test" and
        reserveInfo=None. """
        if reserveName is None and reserveInfo is None:
            raise Exception("Cannot clear all inventory reservations.")
        if reserveName is None:
            cursor.execute("DELETE FROM {} WHERE reserveInfo=?"
                           .format(self._name), (reserveInfo,))
        elif reserveInfo is None:
            cursor.execute("DELETE FROM {} WHERE reservedBy=?"
                           .format(self._name), (reserveName,))
        else:
            cursor.execute("DELETE FROM {} "
                           "WHERE reservedBy=? AND reserveInfo=?"
                           .format(self._name), (reserveName, reserveInfo))
