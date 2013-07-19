import os
from configObj.configobj import ConfigObj
from configObj.validate import Validator
from StringIO import StringIO

class PropertyError(Exception):
    def __init__(self, args):
        super(PropertyError, self).__init__(args)

class RunProperties(object):
    """ This object holds the global variables for the bot, including its
    login information, list of administrators, and the current debug mode. 
    """
    
    login_spec = """# login details should be entered below
    username = string(default=my_username)
    password = string(default=my_password)
    rollover_wait = integer(min=60,default=480)
    """
    
    admin_spec = """# administrator list
    
    [groups]
    # you can create a group, which is a shorthand for a list of permissions:
    exampleGroup = force_list(default=list('permission1','permission2'))
    __many__ = force_list()
    
    [admins]
    # list admins (by PID) here, one per line, with a comma-separated list 
    # of their permissions/groups:
    0 = force_list(default=list('permission1','permission2','group1'))
    __many__ = force_list() 
    """


    version = "0.9.5"
    def __init__(self, debugMode, loginFile, adminFile, 
                 originalDir=os.getcwd(), altLogin=None):
        self.debug = debugMode
        if debugMode:
            print("Debug mode active")
        self.userName = None
        self.userId = None
        self.password = None
        self.clan = None
        self.rolloverWait = 8
        self.connection = None
        self._admins = None
        self._groups = None
        self._adminFile = adminFile
        self._loginFile = loginFile
        self._loadUserNamePassword(altLogin)
        self._loadAdmins()
        self.__originalDir = originalDir

        
    def getAdmins(self, permissionName="*"):
        """ Get a list of all users with the specified permission (or, if
        the permission is "*", all users with any permission) """
        a = set()
        for uid,p in self._admins.items():
            if permissionName == "*" or permissionName.lower() in p:
                a.add(uid)
        return a

        
    def getPermissions(self, uid):
        """ Get a list of all permissions belonging to a user. """
        perms = self._admins.get(uid, set([]))
        if len(perms) > 0:
            perms.append("*")
        return set(perms)


    def refresh(self):
        """ Reload information from login.ini and admin.ini. """
        self._loadAdmins()
        self._loadUserNamePassword(None)
        

    def _loadUserNamePassword(self, altLogin):
        """ Load login.ini """
        c = ConfigObj(self._loginFile, configspec=StringIO(self.login_spec), 
                      interpolation=False, create_empty=True, 
                      raise_errors=True)
        passed = c.validate(Validator(), copy=True)
        c.filename = self._loginFile
        c.write()
        
        if c['username'] == "my_username":
            raise Exception("No login configuration found. Please edit {}."
                            .format(self._loginFile))
        if not passed:
            raise Exception("Invalid login configuration.")
        
        self.userName = c['username']
        self.password = c['password']
        if altLogin is not None:
            self.userName, self.password = altLogin
        self.rolloverWait = c['rollover_wait']
        print("Loaded logon information {}/{}"
              .format(self.userName, "*" * len(self.password)))

        
    def _loadAdmins(self):
        c = ConfigObj(self._adminFile, configspec=StringIO(self.admin_spec), 
                      interpolation=False, create_empty=True,
                      raise_errors=True)
        passed = c.validate(Validator())
        c.filename = self._adminFile
        if not passed:
            raise Exception("Invalid admin configuration.")

        self._groups = dict(c['groups'])
        for g,perms in self._groups.items():
            if g != "exampleGroup":
                print("Added group {} = {}".format(g, ','.join(perms)))

        self._admins = {}
        admins = dict(c['admins'])
        for uid,perms in admins.items():
            permissions = []
            for p in perms:
                permissions.extend(self._groups.get(p, [p]))
            try:
                self._admins[int(uid)] = permissions
            except ValueError:
                raise Exception("Administrators must be listed by player "
                                "ID number.")
            if uid != "0":
                print("Added administrator {} with permissions {}."
                      .format(uid, ','.join(permissions)))
        if len(admins) < 2:
            c.validate(Validator(), copy=True)

        c.write()


    def close(self):
        try:
            os.chdir(self.__originalDir)
        except:
            pass
    
