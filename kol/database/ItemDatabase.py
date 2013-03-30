############# MODIFIED FROM pyKol DISTRIBUTION ##############################

"This module is used as a database for KoL item information."

import kol.Error as Error
from kol.data import Items
from kol.manager import FilterManager
from kol.util import Report

import cPickle as pickle
import os
import datetime

__isInitialized = False
__itemsById = {}
__itemsByDescId = {}
__itemsByName = {}
__discoveryDate = None

discoveryFile = "data/itemDiscovery.dat"

def init():
    """
    Initializes the ItemDatabase. This method should be called before the
    database is ever accessed as it ensures that the database is populated
    with all of the data it needs.
    """
    global __isInitialized
    if __isInitialized == True:
        return

    Report.trace("itemdatabase", "Initializing the item database.")
    returnCode = FilterManager.executeFiltersForEvent("preInitializeItemDatabase")
    if returnCode == FilterManager.FINISHED:
        Report.trace("itemdatabase", "Item database initialized.")
        __isInitialized = True
        return

    for item in Items.items:
        addItem(item)

    FilterManager.executeFiltersForEvent("postInitializeItemDatabase")
    __isInitialized = True
    Report.trace("itemdatabase", "Item database initialized.")

def addItem(item):
    "Adds an item to the database."
    if "plural" not in item:
        item["plural"] = item["name"] + "s"
    __itemsById[item["id"]] = item
    __itemsByDescId[item["descId"]] = item
    __itemsByName[item["name"]] = item

def getItemFromId(itemId):
    "Returns information about an item given its ID."
    if not __isInitialized:
        init()

    try:
        return __itemsById[itemId].copy()
    except KeyError:
        raise Error.Error("Item ID %s is unknown." % itemId, Error.ITEM_NOT_FOUND)

def getOrDiscoverItemFromId(itemId, session):
    try:
        return getItemFromId(itemId)
    except Error.Error:
        discoverMissingItems(session)
        return getItemFromId(itemId)

def getItemFromDescId(descId):
    "Returns information about an item given its description ID."
    if not __isInitialized:
        init()

    try:
        return __itemsByDescId[descId].copy()
    except KeyError:
        raise Error.Error("Item with description ID %s is unknown." % descId, Error.ITEM_NOT_FOUND)

def getOrDiscoverItemFromDescId(descId, session):
    try:
        return getItemFromDescId(descId)
    except Error.Error:
        discoverMissingItems(session)
        return getItemFromDescId(descId)

def getItemFromName(itemName):
    "Returns information about an item given its name."
    if not __isInitialized:
        init()

    try:
        return __itemsByName[itemName].copy()
    except KeyError:
        raise Error.Error("The item '%s' is unknown." % itemName, Error.ITEM_NOT_FOUND)

def getOrDiscoverItemFromName(itemName, session):
    try:
        return getItemFromName(itemName)
    except Error.Error:
        discoverMissingItems(session)
        return getItemFromName(itemName)

def discoverMissingItems(session):
    loadItemsFromFile()
    from kol.request.InventoryRequest import InventoryRequest
    from kol.request.ItemInformationRequest import ItemInformationRequest
    invRequest = InventoryRequest(session)
    invRequest.ignoreItemDatabase = True
    invData = invRequest.doRequest()
    for item in invData["items"]:
        if item["id"] not in __itemsById:
            try:
                itemRequest = ItemInformationRequest(session, item["id"])
                itemData = itemRequest.doRequest()
                item = itemData["item"]
                addItem(item)
                Report.trace("itemdatabase", "Discovered new item: %s" % item["name"])
                
                context = { "item" : item }
                FilterManager.executeFiltersForEvent("discoveredNewItem", context, session=session, item=item)
            except:
                pass
    saveItemsToFile()

def loadItemsFromFile():
    try:
        f = open(discoveryFile, 'rb')
        global __itemsById, __itemsByDescId, __itemsByName, __discoveryDate
        __discoveryDate = pickle.load(f)
        if __discoveryDate is None or (datetime.datetime.now() - __discoveryDate) < datetime.timedelta(days=14):
            __itemsById = pickle.load(f)
            __itemsByDescId = pickle.load(f)
            __itemsByName = pickle.load(f)
        else:
            print("Item cache expired.")
            __discoveryDate = datetime.datetime.now()
        f.close()
        print("Loaded %d items from file." % len(__itemsById))
    except:
        print("Error opening %s for loading" % (discoveryFile))
        __discoveryDate = datetime.datetime.now()
    
def saveItemsToFile():
    try:
        f = open(discoveryFile, 'wb')
        pickle.dump(__discoveryDate, f)
        pickle.dump(__itemsById, f)
        pickle.dump(__itemsByDescId, f)
        pickle.dump(__itemsByName, f)
        f.close()
        print("Wrote %d items to file." % len(__itemsById))
    except:
        try:
            print("Error opening %s for writing" % (discoveryFile))            
            os.remove(discoveryFile)
        except:
            pass
        