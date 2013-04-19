from kol.request.MallItemSearchRequest import MallItemSearchRequest
from kol.request.MallItemPurchaseRequest import MallItemPurchaseRequest
from kol.request.StatusRequest import StatusRequest
from kol.database.ItemDatabase import getItemFromId
import kol.Error
from cwbot.util.tryRequest import tryRequest
from cwbot.locks import InventoryLock


def _empty(txt):
    return


def buyFromMall(session, itemId, quantity=1, maxPrice=0, logFunc=None):
    if logFunc is None:
        logFunc = _empty
    s = tryRequest(StatusRequest(session))
    canBuy = ((  int(s.get('hardcore',"1")) == 0 and
                 int(s.get('roninleft',"1")) == 0) 
              or
                 int(s.get('casual',"0")) == 1 
              or
                 int(s.get('freedralph',"0")) == 1)
    if not canBuy:
        raise kol.Error.Error("Can't buy from mall in Ronin/Hardcore", 
                              kol.Error.USER_IN_HARDCORE_RONIN)

    with InventoryLock.lock:
        item = getItemFromId(itemId)
        itemName = item.get('name', str(itemId))
        numTries = 0
        numBought = 0
        numResults = 10
        logFunc("Trying to buy {}x {} from mall..."
                .format(quantity, itemName))
        while numTries < 10:
            r1 = MallItemSearchRequest(session, 
                                       itemName, 
                                       maxPrice=maxPrice, 
                                       numResults=numResults)
            d1 = tryRequest(r1, numTries=1)
            itemList = [item for item in d1['results']
                        if item.get('id', -1) == itemId]
            listFull = (len(itemList) == numResults)
            availableList = [item for item in itemList
                             if not item.get('hitLimit', False)]
            if not itemList:
                return numBought
            if not availableList and listFull:
                numResults *= 2
            while availableList and numBought < quantity:
                item = availableList[0]
                limitedMode = False
                qty = min(quantity, item['quantity'])
                if 'limit' in item:
                    qty = 1
                    limitedMode = True
                price = item['price']
                storeId = item['storeId']

                logFunc("Buying {}x {} @ {} meat from store {}"
                        .format(qty, itemName, price, storeId))
                r2 = MallItemPurchaseRequest(
                                        session, storeId, itemId, price, qty)
                try:
                    d2 = tryRequest(r2, numTries=1)
                    numBought += d2['items'][0]['quantity']
                    logFunc("Spent {} meat and got {}x {}."
                            .format(d2['meatSpent'], 
                                    d2['items'][0]['quantity'], 
                                    itemName))
                    if not limitedMode:
                        availableList.pop(0)
                except kol.Error.Error as e:
                    if e.code == kol.Error.ITEM_NOT_FOUND:
                        logFunc("Could not buy item. Refreshing...")
                        # refresh search
                        availableList = []
                        continue
                    else:
                        logFunc("Error buying from this store. Moving on...")
                        availableList.pop(0)
                        continue
            numTries += 1
            if numBought >= quantity:
                break
        return numBought
