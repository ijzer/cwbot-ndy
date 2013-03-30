# this file holds the spec for the modules.ini file, to be used by ConfigObj.

MODULE_SPEC = """# module configuration

# If enabled, this configuration file will be automatically overwritten. 
# Your comments will be erased,
# but optional values will be automatically inserted.
overwrite_config = boolean(default=True)

[system]
    communication_interval = integer(min=1,max=60,default=1)
    
    # channel list. The first channel is the "main" channel
    channels = string(default="clan,hobopolis,slimetube")

[director]
    mail_check_interval = integer(min=300,max=1800,default=300)

# There may be multiple managers, each set with different options.
# this means that the configuration below should be TWO LEVELS deep. 
# Level 1 is the individual manager, and Level 2 is the module level. 
# Different managers and modules. have different config options.
# By default, chat messages are processed by ALL modules, but in the order of 
# decreasing priority, while for kmails, only the highest-priority applicable 
# module handles the kmail.
# All modules have a type, priority, and a permission string, as well as
# other optional config values. The permission string makes the module 
# "hidden" to anyone who does not have the matching permission.
#
# Example settings, to load DiceModule on all channels and FaxModule on /clan:
#
#    base = cwbot.managers
#    # persistent state for this manager is stored in data/Manager1.json
#    [[Manager1]]   
#        type = AllChannelManager
#        priority = 1
#        base = cwbot.modules.all
#        sync_interval = 100000
#
#        # persistent state for this module is stored with the name
#        # Module3 inside its manager's .json file
#        [[[Module3]]]  
#            type = DiceModule
#            priority = 10
#            permission = None
#            clan_only = False
#    
#    [[Manager2]]
#        type = ChannelManager
#        priority = 0
#        base = cwbot.modules.clan
#        channel = clan
#        sync_interval = 300
#
#        [[[Module4]]]
#            type = FaxModule
#            priority = 0
#            permission = None
#            fax_check_interval = 15
#            faxbot_timeout = 90
#            url_timeout = 15
#            faxbot_id_number = 2194132
#            fax_list_url = http://goo.gl/Q352Q
#            clan_only = True
#            [[[[alias]]]]
#                lobsterfrogman = lfm
#

    base = string(default="")
    [[__many__]]
        type = string()
        priority = integer(min=0,default=100)
        base = string(default=cwbot.modules)
        sync_interval = integer(min=10, default=300)
        ___many___ = string()
        [[[__many__]]]
            type = string()
            priority = integer(min=0,default=100)
            permission = string(default=None)
            clan_only = boolean(default=False) 

            ___many___ = string()
            [[[[__many__]]]]
                ___many___ = string()
"""