from __future__ import absolute_import
import sys
import os
import time
import signal
import traceback
import logging
import inspect
import socket
import cwbot.util.DebugThreading as threading
from cwbot.util.DebugThreading import _reset_traceback
from cwbot.processArgv import processArgv
from cwbot.sys.BotSystem import BotSystem
from cwbot.common.exceptions import ManualException, ManualRestartException, \
                                    FatalError
from cwbot.kolextra.manager.ChatManager import ChatManager
from cwbot.kolextra.request.SendMessageRequest import SendMessageRequest
from cwbot.kolextra.manager.InventoryManager import InventoryManager
from cwbot.util.tryRequest import tryRequest
from cwbot.database import database
from kol.Session import Session
import kol.Error
from cwbot.sys.database import Database

exitEvent = threading.Event()
databaseName = 'data/cwbot.db'


def openSession(props):
    """ Log in to the KoL servers. """
    log = logging.getLogger()
    s = Session()
    s.login(props.userName, props.password)
    log.info("Logged in.")
    return s


def createChatManager(s):
    """ Open a new chat manager. """
    log = logging.getLogger()
    log.debug("Opening chat...")    
    c = ChatManager(s)
    log.info("Logged in to chat.")
    return c

    
def createInventoryManager(s, db):
    """ Create a new inventory manager. """
    inv = InventoryManager(s, db)
    return inv


def notifyAdmins(s, props, log, etype, value, tb):
    # kmail the administrators
    if props.debug:
        return
    if s is not None and s.isConnected:
        for uid in props.getAdmins('crash_notify'):
            errorText = ''.join(traceback.format_exception(
                                                    etype, value, tb))
            if len(errorText) > 1800:
                errorText = "..." + errorText[-1800:]
                                                    
            alert1 = SendMessageRequest(
                    s, {'userId': uid, 
                        'text': "NOTICE: CWbot encountered an "
                                "unknown error: {}".format(errorText)})
            try:
                log.info("Sending notice to {}".format(uid))
                tryRequest(alert1)
            except Exception:
                log.exception("Exception sending error notice.")


def loginLoop(myDb, props):
    """ Main part of the login loop. """
    global exitEvent
    log = logging.getLogger()
    s = None
    onlineTime = time.time()
    successfulShutdown = False
    fastCrash = False
    cman = None
    try:
        loginWait = 60
        s = openSession(props)
        inv = createInventoryManager(s, myDb)
        cman = createChatManager(s)
        database.flush()
        socket.setdefaulttimeout(60)
        bsys = BotSystem(s, cman, props, inv, 'modules.ini', myDb, exitEvent)
        
        # run the bot main loop. If this function returns, then we are logging
        # out for rollover. If it throws an exception, then we are either
        # shutting down manually or crashing.
        bsys.loop()

        loginWait = props.rolloverWait
        successfulShutdown = True
        log.info("Preparing for rollover...")
    except (SystemExit, KeyboardInterrupt):
        # manual quit
        log.info("Exiting application.")
        loginWait = -1
        successfulShutdown = True
    except FatalError:
        log.exception("Fatal error.")
        etype, value, tb = sys.exc_info()
        notifyAdmins(s, props, log, etype, value, tb)
        del tb
        try:
            cman.sendChatMessage("FATAL ERROR -- Please have the "
                                 "administrator read the error log.")
        except:
            pass
        time.sleep(2)
        log.error("Waiting 60 minutes. Press CTRL+C to exit (or stop the "
                  "service)")
        curTime = time.time()
        onlineTime = 0
        while time.time() - curTime < 3600:
            time.sleep(0.1)
            if exitEvent.is_set():
                break
        raise
    except kol.Error.Error as inst:
        # standard error with a pyKol component
        if inst.code == kol.Error.NIGHTLY_MAINTENANCE and s is None:
            log.info("Nightly maintenance; waiting to try again...")
            loginWait = 60
            successfulShutdown = True
        if hasattr(inst, 'timeToWait'):
            loginWait = inst.timeToWait
        if props.debug:
            log.exception("Exception raised.".format(loginWait))
            raise
        else:
            log.exception("Exception raised; waiting {} seconds."
                          .format(loginWait))
    except ManualException as inst:
        # die for some amount of time
        if hasattr(inst, 'timeToWait'):
            loginWait = inst.timeToWait
        if props.debug:
            log.exception("Exception raised.".format(loginWait))
            raise
        log.exception("Exception raised; waiting {} seconds."
                      .format(loginWait))
        successfulShutdown = True
    except ManualRestartException:
        # restart the process
        loginWait = -2
        successfulShutdown = True
        log.info("Restarting process...")
    except:
        log.exception("Unknown error.")
        etype, value, tb = sys.exc_info()
        notifyAdmins(s, props, log, etype, value, tb)
        del tb
        if props.debug:
            raise
    finally:
        # shut down
        sys.last_traceback = None
        log.debug("Shutting down...")
        if not successfulShutdown and time.time() - onlineTime < 300:
            # if shutdown was too fast: do an exponential back-off
            fastCrash = True
            if s is not None:
                log.warning("Immediate crash detected. "
                            "Backing off before next startup.")
                if not props.debug:
                    try:
                        cman.sendChatMessage("I seem to have crashed quite"
                                             " quickly. I'll try again "
                                             "in a little while.",
                                             useEmoteFormat=True)
                    except:
                        pass
        if cman is not None:
            try:
                log.info("Closing chat...")
                cman.close()
                cman = None
            except:
                log.exception("Error closing chat session.")
        if s is not None:
            try:
                log.info("Closing session...")
                s.logout()
            except:
                log.exception("Error closing KoL session.")
            s = None
        log.info("----- Logged out. -----\n")
    return (loginWait, fastCrash)

    
def signalHandler(signum, stackFrame):
    global exitEvent
    print("\n"
          "******************************************\n"
          "* Preparing to shut down, please wait... *\n"
          "******************************************\n")
    exitEvent.set()


def main(curFolder=None, connection=None):
    import __main__
    if curFolder == None:
        curFolder = os.path.dirname(os.path.abspath(inspect.getfile(__main__)))
    props = processArgv(sys.argv, curFolder) # set current folder
    props.connection = connection
    crashWait = 60
    myDb = Database(databaseName) 
    loginWait = 0
    log = logging.getLogger()
    logging.getLogger("requests").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.INFO)

    # register signals
    signal.signal(signal.SIGTERM, signalHandler)
    signal.signal(signal.SIGINT, signalHandler)
    try:
        # windows signals
        signal.signal(signal.CTRL_C_EVENT, signalHandler)
        signal.signal(signal.CTRL_BREAK_EVENT, signalHandler)
    except:
        pass
    
    try:
        while loginWait >= 0 and not exitEvent.is_set():
            ### LOGIN LOOP ###
            if loginWait > 0:
                log.info("Sleeping for {} seconds.".format(loginWait))
                time.sleep(loginWait)
                props.refresh()
            
            # main section of login loop
            if exitEvent.is_set():
                break
            (loginWait, fastCrash) = loginLoop(myDb, props)
            if fastCrash:
                # fast crash: perform exponential back-off
                crashWait = min(2*60*60, crashWait*2)
                loginWait = crashWait
                log.info("New crash wait: {}".format(crashWait))
            else:
                # reset exponential back-off
                crashWait = 60
            _reset_traceback()
    except:
        raise
    finally:
        # close a bunch of stuff
        log.info("Main thread done.")
        
        # wait for other threads to close
        threads = [t for t in threading.enumerate() if t.daemon == False]
        numThreads = len(threads)
        delayTime = 0
        log.info("Waiting for threads to close: {}".format(threads))
        while numThreads > 1:
            try:
                time.sleep(delayTime)
                delayTime = 0.25
                if props is not None:
                    try:
                        props.close()
                    except:
                        pass
                threads = [t for t in threading.enumerate() 
                           if t.daemon == False]
                numThreadsNew = len(threads)
                if numThreadsNew != numThreads:
                    log.debug("Waiting for threads to close: {}"
                             .format(threads))
                numThreads = numThreadsNew
            except:
                pass

        log.info("-------- System Shutdown --------\n")            
        if loginWait == -2:
            if props.connection is not None:
                props.connection.send("restart")
            else:
                # restart program
                log.info("Invoking manual restart.")
                python = sys.executable
                os.execl(python, python, *sys.argv)
        else:
            if props.connection is not None:
                props.connection.send("stop")

        try:
            props.connection.close()
        except Exception:
            pass
