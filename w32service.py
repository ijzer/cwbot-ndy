import win32service #@UnresolvedImport
import win32serviceutil #@UnresolvedImport
import win32api #@UnresolvedImport
import win32con #@UnresolvedImport
import win32event #@UnresolvedImport
import win32evtlogutil #@UnresolvedImport
import os, sys, string, time
import re
import multiprocessing
import cwbot.main


class CwbotService(win32serviceutil.ServiceFramework):

    curFolder = os.path.dirname(os.path.abspath(__file__))
    paths = curFolder.split('\\')

    _svc_name_ = "cwbot_{}".format(curFolder.replace('\\', '|')[:240])
    _svc_display_name_ = "cwbot - KoL chatbot ({})".format(curFolder)
    _svc_description_ = ("Chatbot for the Kingdom of Loathing; "
                         "distribution located in {}".format(curFolder))

    
    def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self._connection = None
            self._proc = None
                       

    def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.hWaitStop)                    
          
          
    def SvcDoRun(self):
        curFile = __file__
        paths = re.split(r'[/\\]', curFile)
        curFolder = '\\'.join(paths[:-1]) + "\\"
        try:
            os.chdir(curFolder)
        except:
            f = open("error.txt", 'w')
            f.write("ERROR changing to folder: {}".format(curFolder))
            raise
        try:
            os.mkdir("log")
        except:
            pass
        
        import servicemanager #@UnresolvedImport
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                            servicemanager.PYS_SERVICE_STARTED,
                            (self._svc_name_, '')) 
      
        # This is how long the service will wait to refresh itself, in millisec
        self.timeout = 30000    

        running = True
        firstStartup = True
        servicemanager.LogInfoMsg("-- Starting main loop --")
        while running:
            waitTime = 1000 if firstStartup else self.timeout
            firstStartup = False
            
            servicemanager.LogInfoMsg("Waiting for event...")
            # Wait for service stop signal, if I timeout, loop again
            rc = win32event.WaitForSingleObject(self.hWaitStop, waitTime)
            # Check to see if self.hWaitStop happened
            if rc == win32event.WAIT_OBJECT_0:
            # Stop signal encountered
                servicemanager.LogInfoMsg("Stop signal raised.")
                if self._proc is not None and self._proc.is_alive():
                    try:
                        servicemanager.LogInfoMsg("Sending stop signal to "
                                                  "child process...")
                        self._connection.send("stop")
                    except Exception:
                        pass
                    self._proc.join(300)
                        
                    if self._proc.is_alive():
                        servicemanager.LogInfoMsg("Stop signal timed out. "
                                                  "Terminating...")
                        self._proc.terminate()
                    self._proc.join()
                    servicemanager.LogInfoMsg("Process joined.")
                        
                servicemanager.LogInfoMsg("cwbot - STOPPED")  #For Event Log
                break
            else:
                servicemanager.LogInfoMsg("No stop signal.")
                if self._proc is None:
                    reload(cwbot.main)
                    servicemanager.LogInfoMsg("Creating child process...")
                    self._connection, c = multiprocessing.Pipe()
                    self._proc = multiprocessing.Process(
                                     target=cwbot.main.main,
                                     args=(curFolder, c))
                    self._proc.start()
                    servicemanager.LogInfoMsg("Process started.")
                    time.sleep(5)
                if not self._proc.is_alive():
                    servicemanager.LogInfoMsg("Process died.")
                    s = "stop"
                    try:
                        while self._connection.poll():
                            s = self._connection.recv()
                            servicemanager.LogInfoMsg("Received from child "
                                                      "process: {}"
                                                      .format(s))
                    except EOFError:
                        pass
                    if s == "restart":
                        self._proc = None
                        self._connection = None
                        firstStartup = True
                        servicemanager.LogInfoMsg("restarting...")
                    else:
                        running = False
                        servicemanager.LogInfoMsg("ending...")
 
 
def ctrlHandler(ctrlType):
    return True
                  
if __name__ == '__main__':   
    win32api.SetConsoleCtrlHandler(ctrlHandler, True)   
    retval = win32serviceutil.HandleCommandLine(CwbotService)
    sys.exit(retval)
