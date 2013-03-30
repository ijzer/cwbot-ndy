User's manual for CWbot
-----------------------


0. Installation
---------------

If you don't have Python, you can install it from http://www.python.org/ or
by using your package manager if you run Linux. CWbot requires the latest
version of Python 2. As of this time, this is Python version 2.7. CWbot
is not compatible with Python 3.


Copy all files to an empty folder.
If you have python's pip module installed, run the following command in
your terminal:

pip install -U -r requirements.txt
(you may need administrator permissions)


If you don't have pip, you can run the following command:

easy_install pip


If you also don't have easy_install, you can install it by installing
setuptools from https://pypi.python.org/pypi/setuptools. Then run:

easy_install pip 
pip install -U -r /path/to/cwbot/requirements.txt


(or, on windows, run the following from c:\Python27:)
Scripts\easy_install pip
Scripts\pip install -U -r C:\path\to\cwbot\requirements.txt


The steps on OSX are probably similar.


1. Setting up CWbot for logon
-----------------------------

CWbot requires a dedicated KoL account to run. You must know the username and
password of the account. 

IMPORTANT: The account's timezone must be set to US/Arizona. Please go into
options > account settings and select US/Arizona as the time zone.

ALSO IMPORTANT: The account must not have broken its magical mystical hippy
stone. Many of CWbot's inventory features work from main inventory. The bot
will inevitably crash when an item gets stolen in PVP. If you want a PVP bot,
you'll have to write your own.

Place account information in 
admin.ini, which has the following format (ignore lines in <> angle braces):

<Beginning of file admin.ini>
username = (account username)
password = (account password)
clan_id = (the clan ID of your clan. For example, Noblesse Oblige = 4242)
rollover_wait = (number of seconds to wait at rollover; default = 480)
<End of file admin.ini>

To start the bot - at the command line type:
"python cwbot.py path/to/cwbot" (without the quotes).

If in the correct folder already, use "python cwbot.py ." instead.
On windows, you may need to instead type "c:\Python27\python cwbot.py ."

(To run in debug mode, use "python cwbot.py path/to/cwbot debug")


1A. Running CWbot as a service
------------------------------

If you want to run CWbot to run at startup, you should set it up as a service.

If you are using Ubuntu Linux, an Upstart configuration file is included in 
the doc folder. Simply copy this into your /etc/init folder and reboot, or
use "sudo service cwbot start" to start the service. If your Linux
distribution does not include Upstart, you will have to set up your own
init.d or systemd script.

If you are using Windows, the easiest way to start CWbot as boot is using the
Windows Task Scheduler, which can be found in 
Control Panel > Administrative Tools > Task Scheduler
Then create a new Task with the following settings:
General: click "run whether user is logged in or not"
Triggers: New..., begin at startup, uncheck "stop task if it runs longer than"
Actions: New..., program="C:\Python27\python.exe", 
				 arguments="c:\path\to\cwbot\cwbot.py ."
				 start in="c:\path\to\cwbot\"
Settings: Uncheck "stop the task if it runs longer than"
		  check "if the running task does not end, force it to stop"
		  set "if the task is already running..." to "stop existing instance"
Then click OK, select task in task scheduler library, right click -> run
This doesn't work quite as well as with Linux, because if you stop your
computer the bot won't say goodbye. In a future version this might be
improved.

If you have a Mac, there must be some way to do this.


2. Setting up CWbot with modules
--------------------------------

CWbot is designed with a Director > Manager > Module heirarchy that
is configured from modules.ini. There is a single Director, which sends and
receives chat and kmail communications. The Director loads several managers, 
which extract "interesting" communications and ignore others. In turn, 
each manager may load any number of modules. Each module processes chat or 
kmails in a certain way. Managers and modules have a priority value, which 
affects the order in which they process information. To be more specific:

Director: The highest level. The director is in charge of three things:
	first, it is in charge of loading its managers based on configuration
	settings. Second, it is in charge of receiving new chats/kmails and
	passing them to the managers. Third, it is in charge of cleanup when
	the bot shuts down. 
	
Manager: The middle level. The managers filter and distribute 
	chats/kmails to their modules, and also provide upkeep and data 
	functions for the modules. They are also in charge of initializing 
	and cleaning up the modules. Different managers may provide different
	functions to their modules; for example, the HoboChannelManager polls
	the clan Hobopolis logs and supplies this information periodically
	to its modules, and separates chats from the dungeon from user
	chats. The MessageManager receives kmails. In general, managers that 
	handle chat do not handle kmails, and vice versa.
	
Module: The lowest level. A module provides a single function. For example,
	the FaxModule tells users what is in the fax machine and announces
	if a new fax has arrived, while the DiceModule allows users to roll dice
	or shuffle a list of items. Some modules require specific manager
	functions; for example, the modules in cwbot.modules.hobopolis must
	have a HoboChannelManager as their parent manager, since they rely on
	periodic Hobopolis logs. In general, modules that process kmails and
	chats must be under the appropriate type of manager.


2A. Modules.ini format
----------------------

The modules.ini file has most configuration options. The general format is
as follows:

[system]
	(system options)
	
[director]
	(director options)
	[[ManagerA_name]]
		(ManagerA settings)
		[[[Module1_name]]]
			(Module1 settings)
		[[[Module2_name]]]
			(Module2 settings)
	[[ManagerB_name]]
		(ManagerB settings)
		[[[Module3_name]]]
			(Module3 settings)
	
Manager settings perform most of the "hard work" and are where managers
and modules to load are placed. Here is an example setting:

[system]
    channels = clan,hobopolis,slimetube
[director]
	base = cwbot.managers
   	[[kmail_manager]]
		type = MessageManager
        base = cwbot.modules.messages
        sync_interval = 300
        channel = clan
        [[[Donate]]]
            type = DonateModule
            priority = 111
            permission = None
            clan_only = False
        [[[Not-In-Clan]]]
            type = NotInClanModule
            priority = 110
            permission = None
            clan_only = False
        [[[Hookah-Kmail]]]
            type = HookahKmailModule
            priority = 105
            permission = None
            clan_only = True
            save_last = 1
            message_channel = clan
        [[[Unknown]]]
            type = UnknownKmailModule
            priority = 100
            permission = None
            clan_only = False
    [[all_channel]]
        type = AllChannelManager
        priority = 110
        base = cwbot.modules
        sync_interval = 300
        accept_private_messages = True
        [[[Dice]]]
            type = general.DiceModule
            priority = 100
            permission = None
            clan_only = False
        [[[Maintenance]]]
            type = general.MaintenanceModule
            permission = admin_command
            priority = 100
            clan_only = False
        [[[Announce]]]
            type = general.AnnouncementModule
            priority = 0
            permission = None
            clan_only = False
            [[[[clan]]]]
                startup = All systems online.
                shutdown = Happy rollover!
                crash = Oh my, I seem to have crashed. (%arg%)
                manual_stop = I am going offline for some maintenance. See you soon!
                manual_restart = Restarting bot...
            [[[[hobopolis]]]]
                startup = Hobo-detection engaged.
                shutdown = Happy rollover!
                crash = Oh my, I seem to have crashed. (%arg%)
                manual_stop = I am going offline for some maintenance. See you soon!
                manual_restart = Restarting bot...
        [[[Breakfast]]]
            type = general.BreakfastModule
            priority = 100
            permission = None
            clan_only = False
            vip = True
            clovers = True
        [[[Shutdown]]]
            type = general.ShutdownModule
            priority = 10
            permission = None
            clan_only = False
            shutdown_time = 3
    [[hobopolis]]
        type = HoboChannelManager
        priority = 106
        channel = hobopolis
        base = cwbot.modules
        log_check_interval = 15
        sync_interval = 300
        accept_private_messages = True
        [[[Cage]]]
            type = hobopolis.CageModule
            permission = None
            priority = 100
            clan_only = True
        [[[Sewer]]]
            type = hobopolis.SewerModule
            priority = 100
            permission = None
            clan_only = True
        [[[Turns]]]
            type = hobopolis.TurnsModule
            priority = 101
            permission = None
            clan_only = True

			
A summary of what this specifies:
- The Director loads three managers: a MessageManager named ,
	an AllChannelManager named all_channel, and a HoboChannelManager named
	hobopolis.
	(The full type name of the first manager is 
	cwbot.managers.MessageManager.MessageManager. This is defined by the 
	MessageManager class in cwbot/managers/MessageManager.py.
	Note that CWbot automatically loads the class that matches the filename.) 
	The internal name for this manager is kmail_manager, but any unique text
	string may be specified. The identifier is used for logging and other
	internal purposes. Note that the director can have multiple managers 
	loaded by placing other manager entries, one after another.
- The 'base' option of the director specifies the base package from which
	to load managers; in this case, it is cwbot.managers. Managers also have
	a 'base' option, from which to load modules. All modules will be loaded 
	out of this base package, so for example the last module in the list for
	the MessageManager is cwbot.modules.messages.UnknownKmailModule.
- The 'sync_interval' option sets how often module state is written to disk,
	in seconds. The module settings will be synchronized every 300 seconds,
	which is the default setting.
- The 'channel' option sets what channel is the default channel for
	announcements. Even though this is a kmail-based manager, modules still 
	have the capability to send chat messages.

Under the MessageManager options is the list of modules to be loaded.
Here is what happens for the first setting (Donate):
- The module to be loaded is cwbot.modules.messages.DonateModule. This module
	will be assigned the internal identity "Donate".
- The Donate module does the following: If a Kmail contains the word "donate",
	the bot keeps any items attached and replies with a thank you message.
	Otherwise, it does nothing, and the next-lowest priority module handles
	the kmail.
- The module is loaded with priority 111. This is higher than the other
	modules in the list, so all kmails will be handled by this module first.
- The module's permission is set to None. Some modules can be configured to
	require a permission. Permissions are set through the admin.ini file.
	If a permission is set, the MessageManager will skip that module
	when handling kmails from users without that permission. The special
	permission * matches any permission, so any user with one permission
	may use such a module.
- The modules's clan-only status is set to False. This setting works the
	same way as permission: any users who do not have a matching clan_id
	will not be able to interact with this module.
	
Some modules have other settings: for example, the HookahKmailModule has
the save_last and message_channel settings. These settings vary by module,
but are either documented in the doc files or in their own file.

The chat portion of the configuration does the following:
- The ChatDirector listens to three chat channels: clan, hobopolis, and
	slimetube. The first channel (clan) is the "main" chat channel.
- The ChatDirector loads two managers: a cwbot.managers.AllChannelManager
	with identity name "all_channel", and a cwbotlmanagers.HoboChannelManager
	with identity name "hobopolis". Note that the 'base' config option
	is not allowed for the KmailDirector, but is allowed for the ChatDirector.	
- In addition to the settings already outlined in the Kmail section, both
	managers are configured to accept private messages and have a priority
	value. Chats are passed to managers in order of priority, and the
	managers in turn pass chats to their modules in order of priority.
- The AllChannelManager loads five modules. The DiceModule has no interesting
	configuration options. The BreakfastModule and ShutdownModule have
	their own options, but are otherwise uninteresting as well.
- The AllChannelManager loads the MaintenanceModule with a permission
	setting. Only a user in admin.ini with the admin_command permission
	may interact with the MaintenanceModule; its commands will not show
	up in !help to other users, and the manager will return an access
	denied message if an unpriviliged user attempts to use a command
	from the module.
- The AllChannelManager loads AnnouncementModule. This module has many
	options in its configuration, in two subsections.
- The HoboChannelManager is configured to respond only to messages on 
	/hobopolis. It is also configured to poll the raid logs every 15 seconds.
- All of the modules under the HoboChannelManager are configured to be
	clan-only, so if someone outside the clan sends a PM to try to get
	Hobopolis state information, their request will be denied.
	
Note that most modules are intended to only instantiated one time, especially
chat-based modules. A few are "reusable" and it is OK to load multiple copies.
For example, the included KeywordModule can be reused because it has a
customizable !command. In addition, the HookahKmailModule can be loaded
multiple times, for example to allow out-of-clan users to also use it, but
with a more expensive trade ratio. 
	
	
2C. The Communication System
----------------------------

The Director downloads all new chats and kmails, and is responsible for
transmitting all chats and kmails. All new communications are passed to the
Managers, in order of decreasing priority. Each manager independently decides
whether a chat/kmail is "interesting", based on its own criteria. For example,
the SingleChannelManager filters out chats by their channel. If a chat is 
received on a different channel, that particular manager will not forward 
the chat to its modules. Chat-based managers may also be configured 
to reply to PMs. Once a manager decides to process a communication, it is
passed to its modules in a systematic way. For example, the chat-based
managers pass the chat to every module, collect all the replies, and transmits
each one as a separate chat. The MessageManager passes new kmails to its
modules in order of priority, but stops as soon as one module sends a reply. 

Managers also allow extended capabilities. For example, 
the HoboChannelManager polls the clan raid logs and updates its modules 
with this information. "Normal" modules will work when loaded by the 
HoboChannelManager, but modules designed to work with the HoboChannelManager
will not work when loaded by a chat manager without that capability.

Chats are handled differently than Kmails. Most chats in a chatroom are
not directed at CWbot, but are general chat. CWbot interprets any
chat starting with a ! symbol as a command directed at the bot. Most 
chat-based modules respond to various !commands. For example, sending a 
chat "!fax" in the appropriate channel will be interpreted by the bot as a 
the command "fax", a command which is ignored by all modules except the 
FaxModule. Chats without an ! symbol are interpreted as non-commands. Modules 
may* still process these, but in general they are ignored.

Some commands may have arguments. For example, "!roll 1d10+2d6" is interpreted
as a "roll" command with argument "1d10+2d6". If a user has a chat effect,
they may also use "!roll (1d10+2d6)" for the same effect; anything after the
parentheses is ignored.

As previously stated, the chat-based managers included handle chats and 
priority differently than the MessageManager. When the MessageManager
processes a Kmail, it first sends the kmail to its highest-priority module,
which can choose to respond to the kmail or ignore it. If it responds, the
MessageManager sends the reply to the director; if it ignores the kmail, it
is passed to the next-highest priority module. This process is repeated until
either a module replies, or every module has ignored the message (in which
case, nothing happens). However, when a chat is received, it is passed to 
each manager in order of priority. The MessageManager ignores chats, but
the other managers do not. Each manager may either handle or discard the chat 
message based on some manager-specific criteria. If the chat is handled, the 
manager passes it to every module in order of priority, but unlike with the 
MessageManager, every module receives the chat, even if a higher-priority
module has also responded. In this way, multiple modules may reply to the 
same command.

Note that there is a special command !help. This command is handled by
chat-based managers directly and shows help for commands.

*Modules set to clan-only will only process !commands that match their
built-in available commands, not non-commands. In most cases this is not an
issue.


                                 New comm.
                                    |
								    v
-------------------------------------------------------------------------------
|                                Director                                |
-------------------------------------------------------------------------------
                |                                            |
                | comm                ...                    | comm
                v                                            v
-------------------------------------     -------------------------------------
|          Manager 1                | ... |             Manager N             |
-------------------------------------     -------------------------------------
       |                    |  comm              |                    | comm
       |  comm + data       |   +                | comm + data        |  + 
       v                    v  data              v                    v data
  ------------         ------------         ------------         ------------
  | Module 1 |   ...   | Module N |         | Module 1 |   ...   | Module N |
  ------------         ------------         ------------         ------------
  
  
3. Available Managers and Modules
---------------------------------

3A. For Kmails
--------------

Managers: 

cwbot.managers.MessageManager - the only included manager for processing 
	Kmails. This manager processes kmails in a "waterfall" fashion as
	described above. Once a module successfully processes a kmail, 
	lower-priority modules will not get a chance to process them.
	
	
Modules (default options in parentheses):

cwbot.modules.DonateModule - processes a Kmail if it has the word "donate" in
	it. If it does, the bot keeps all attached items and sends a thank-you
	kmail.
	(No options)
	
cwbot.modules.messages.HookahKmailModule - runs the bot's hookah exchange. 
	Users may send in a user-defined number of hookah parts in exchange for one
    of each (e.g., send in 6 walrus ice creams to get one of all 6 hookah 
	parts).
	Options: save_last: how many hookah sets to keep in reserve (1)
	         message_channel: if not "none", announce a congratulatory
							  message on the specified chat channel (clan)
			 n: total number of items required for a trade (6)
			 resends: number of EXTRA times a player is allowed to
			 			trade for a hookah (0)
			 
cwbot.modules.messages.HookahKmailModule.HookahDonateKmailModule - special 
	donation module for the hookah exchange. If someone sends a message with 
	"donate" in the text, and it has hookah parts, the bot will send a special 
	thank-you message and announce the hookah donation in the specified chat 
	channel. Make sure this has a higher priority than DonateModule, or it will
	never be triggered.
	Options: message_channel: same function as HookahKmailModule (clan)
	
cwbot.modules.messages.NotInClanModule - A module that checks if a Kmail is
	from someone not in the same clan. If the player is not in the same clan,
	it sends a message back that informs them so. Any modules with lower
	priority than this module can't be accessed by non-clan members if
	you are using the MessageManager (since this module will always process
	their kmail)
	
cwbot.modules.messages.SgeeaModule - A module that handles donation of
	soft green echo eyedrop antidotes. If someone sends a Kmail with a
	SGEEA attached, the bot will automatically keep them and send back
	any other attachments.
	
cwbot.modules.messages.UnknownKmailModule - A module that replies
	to any Kmail with "I don't understand your request.". This module
	is a sort of catch-all and should be the lowest-priority module.
	
cwbot.modules.messages.CashoutModule - A module that handles balances and
	cashing out. When the bot tries to send a Kmail and fails (usually due
	to the player being in Ronin or Hardcore), it sends a notification
	and holds on to the items. A player can send a kmail with "balance" in
	the text to get a list of items owed, and "cashout" to have the bot
	send them their items. The CashoutModule handles both of these.


3B. For Chat
------------

Managers:

cwbot.managers.MultiChannelManager - A manager that only responds to chats
	on certain channels, configured with the manager's 'channel' option. Can
	also be configured to accept private messages. To handle multiple
	channels, use a comma-separated list. The first channel in the list is
	the "default" channel. Don't use a slash. For example, to chat in /clan
	and /games, specify "channel = clan, games"
	
cwbot.managers.HoboChannelManager - A special MultiChannelManager that 
	interacts with the clan raid log. The modules in cwbot.modules.hobopolis 
	require this functionality to run properly. It must still be configured
	with a 'channel' option. It's HIGHLY recommended you only have one of
	these. No man knows the horrors that await a bot with multiple
	HoboChannelManagers. Also, you should make hobopolis the default channel
	by making it the first on the channel list, if you use multiple channels.
	
cwbot.managers.AllChannelManager - A manager that responds to chats received
	on any channel (assuming the bot is listening to that channel). The
	bot's listening channels are specified in the [system] section of
	modules.ini. The first channel is the "main" channel and used for
	some error messages and other stuff.
	

Modules (default options in parentheses):

cwbot.general.AnnouncementModule - A module that announces system events in
	chat. For example, it can announce when the bot logs off for rollover,
	when it comes online, or when it crashes. The configuration format is as
	follows:
	
	[[[Announce]]]
		type = general.AnnouncementModule
		[[[[channelname-1]]]]
			event1 = message1
			event2 = message2
		[[[[channelname-2]]]]
			event1 = message1
			event2 = message2
	
	Here channelname-N is a chat channel like "clan" or "hobopolis". The
	possible events are currently: startup (when bot comes online),
	shutdown (when bot shuts down for rollover), crash (when bot has an 
	error), manual_stop (when bot is killed on its server), manual_restart 
	(when bot is restarting due to administrator command). The message text 
	can include some special substitutions: %arg% is replaced with any
	arguments to the event (though, the only one with any arguments right now
	is the crash event). This module does not pay attention to chat at all
	and can be placed under any Manager, but you don't need more than one.
	
cwbot.modules.general.BreakfastModule - A module that doesn't process chats, 
	but grabs meat and items from the clan lounge and buys clovers when
	the bot first logs on. It can be placed under any manager, and you
	should only have one.
	Options: clovers: if true, buy clovers from hermit (true)
	         vip: if true, try to get items from VIP lounge (true)
			 
cwbot.modules.general.ChatLogModule - A module that keeps a running log of 
	all chats. Users can send a "!chatlog" chat to request the last few lines
	of chat sent in their channel, or "!chatlog CHANNELNAME" to see chats
	from another channel. This module also logs chats to text files in
	the log/ director.
	Because of the way that chats work, this module should have the highest
	priority of any module, or replies from higher-priority modules will
	show up above their commands. This means that the ChatLogModule needs
	to be in the highest-priority manager and have the highest priority
	out of all of that manager's modules. Because it uses an !command, you
	should only have one of these, and it's recommended that it be under
	the AllChannelManager. It's possible to set some channels as clan-only,
	for which out-of-clan users can't read the messages.
	Options: clan_only_channels: a list of channels for which only clan 
		members may request logs (clan, hobopolis, slimetube)
	
cwbot.modules.general.DiceModule - A module that has several functions related 
	to random number generation. Users can use "!roll MdN" expressions to
	roll dice. Expressions can use +-*/()^ to combine dice expressions.
	Users can also type "!roll item1, item2, item3, item4" to choose an
	item from a list. There is also a second command:
	"!permute item1, item2, item3, item4" randomly shuffles a list.
	You should only use one of these.
	(No options)
	
cwbot.modules.general.FaxModule - A module that handles faxing. Users can
	send "!fax" to check what is in the fax machine and how long it has
	been there. The module has two modes of operation: announce mode and
	silent mode. 
	
	Announce mode: When a new fax is received, the bot will announce it
		in chat. Also, if a user does not know the code for a monster
		they want to fax, they can send, in chat, the message
		"!fax MONSTERNAME" and the FaxModule will use fuzzy matching to
		determine what monster they want and automatically request it
		from Faxbot, then announce when the fax has arrived.
		IMPORTANT: To use announce mode, Faxbot must be added as an
				   admin in admin.ini and have permission "clan" if
				   you limit this module to clan-only. That is, add the line:
				   2194132 = clan
				   to your admin.ini file.
	
	Silent mode: The bot will not announce new faxes in chat. Users can
		use "!fax MONSTERNAME" to get the monster code for a Faxbot
		request, but the bot will not automatically request it.
		
	Note that Faxbot only allows 20 requests per day, so after that,
	the module will not automatically request faxes in announce mode
	until the next day. Since announce mode needs to read private
	messages from FaxBot, it will not work if the FaxModule's parent
	manager has disabled private messages.
	You should only use one of these, and it's recommended you place it
	in a MultiChannelManager that is limited to /clan if you are using
	announce mode. This will necessarily limit fax requests to clannies.
	Otherwise, be sure to set "clan_only = true" in its configuration, as 
	well. If you are using silent mode, this is not necessary, since it will
	not actually request faxes.
	Options: fax_check_interval: how often, in seconds, to check fax log (15)
             faxbot_timeout: how long to wait for a fax request (90)
             url_timeout: how many seconds to try to load fax list (15)
             faxbot_id_number: userID for faxbot (2194132)
             fax_list_url: kolspading fax list (http://goo.gl/Q352Q)
             announce: true for announce mode, false for silent mode (true)
	
cwbot.modules.general.HookahInfoModule - A module that reports on how
	many hookahs are available using the "!hookah" command. Detailed
	stats are available with "!hookah stock". You should only need one of
	these.
	Options: save_last: same function as HookahKmailModule (1)
	
cwbot.modules.general.HookahOverrideModule - An administrative module
	that sends a set of hookah parts to a user using the command
	"!hookah_override USERID". It is highly recommended that this
	module be protected by a permission setting.
	Options: save_last: same function as HookahKmailModule (1)
	
cwbot.modules.general.KeywordModule - A module that displays
	informational chat messages to users. This module has
	a configurable command, so multiple may instances
	may be loaded and accessed with different commands.
	
	This module is configured as follows:
    [[[Module-Identity-Name]]]
        type = KeywordModule
        command = COMMANDNAME
        helptext = HELPTEXT
        [[[[text]]]]
            __default__ = Default text shown if no argument supplied.
            __error__ = Message shown if no matches.
            __unique__ = Messge shown if more than one match.
            keyword1 = Text1
			keyword2 = Text2
			
	Users can query this module with "!COMMANDNAME KEYWORD", where COMMANDNAME
	is the option shows in the config. If KEYWORD matches one of the keywords
	uniquely, that text will be shown. If no keyword is supplied, the
	__default__ text is shown instead. HELPTEXT is shown if the user sends
	"!help COMMANDNAME".
			
	Some special variables may be used in the text: %arg% is replaced with
	the argument to the command. %keywords% is replaced with a comma-separated
	list of available keywords. %num% is used only in __unique__, and is
	replaced with the number of matches.
	
	Since this module has a variable command name, it is possible to use
	multiple copies to do different things; for example one might show
	rules about Hobopolis and another might show helpful clan links.
	
cwbot.modules.general.MaintenanceModule - Holds maintenance commands. It's
	highly recommended this is protected with permissions. Available commands
	are "!die N" to raise an exception and log out for N minutes; "!restart"
	to restart the bot (this is different from !die; the codebase is 
	reloaded); "!simulate MESSAGE" to simulate system messages and dungeon
	messages; and "!raise_event EVENT" to debug the event subsystem.
	(No options)
	
cwbot.modules.general.MiscClanModule - Misc. functions for /clan. Right
	now it only has the "!donate" command, which shows how to donate stuff.
	(No options)
	
cwbot.modules.general.MiscCommandModule - Some silly functions that don't
	really have a major function.
	(No options)
	
cwbot.modules.general.PermissionsModule - Shows a user's permissions with
	the "!permissions" command. If you want to "hide" this from normal
	users, set it with a permission setting of *.
	(No options)

cwbot.modules.general.ShutdownModule - This module catches messages from
	KoL about rollover, and shuts down the bot when rollover gets close.
	(The bot will attempt to log on after the number of seconds specified
	in login.ini, and every minute thereafter, until it comes back online.) 
	If a ShutdownModule is not loaded, the bot will just stay online until 
	rollover, and 	then crash. This isn't terrible, and the bot will come 
	back online, but it's much messier and some persistent state may be lost.
	Don't set shutdown_time to more time than specified in login.ini, or the 
	bot may come online right before rollover and then crash. You should
	only load one of these.
	Options: shutdown_time: amount of time, in MINUTES, before rollover 
							that the bot should shut down (3)
							
cwbot.modules.general.StateModule - A maintenance module for inspecting
	persistent state of other modules. It's recommended that this
	module be protected by permissions, as it can be a bit spammy.
	A user can send a message "!state" and the module will print
	out the state of all persistent modules. The command
	"!state __MODULE-IDENTITY__" can be used to display only the state
	of a specific module. The double-underscores are mandatory. Or you could
	type "!state MODULE-NAME", but you need to know the programmatic name
	of the module.
	(No options)
	
cwbot.modules.general.UneffectModule - A module that can be used to
	remove chat effects from the bot. Users can type "!uneffect" to
	get a list of the bot's current effects, and if the bot has a chat
	effect, they can use "!uneffect EFFECT_ID" to remove the effect,
	if the bot has any SGEEAs. If this is abused by trolls, it might
	be wise to make this module clan-only.
	Options: auto_remove: comma-separated list of effect ids to be
						  autoremoved (697)
	

Hobopolis modules (all require the HoboChannelManager):
NOTE: All of these modules should not be loaded more than once.

cwbot.modules.hobopolis.AhbgModule - Tracks progress in the Ancient
	Hobo Burial Ground. Specifically, this module tracks the number
	of available dances/watches and how much damage players have
	done. Users can type "!ahbg" or "!burial" to see how many dances
	remain, and how many watches/dances they have done. It is
	also possible to type "!ahbg USERNAME" to see how other players
	are doing.
	(No options)
	
cwbot.modules.hobopolis.BurnbarrelModule - Tracks progress in
	Burnbarrel Blvd. Specifically, this module tracks how tall the
	tire stack is and how much damage it does. If the bot goes offline
	and a tirevalanche occurs while it is offline, it will make an
	appropriate guess as to how much damage was dealt. Users can
	use "!tires" or "!burnbarrel" to check the tire height.
	(No options)
	
cwbot.modules.hobopolis.CageModule - Tracks the C.H.U.M. cage in
	the sewers. Specifically, the bot will track when someone is
	trapped in the cage, when they are released, and if they have
	left the cage. Users can type "!cage" to see if the cage is
	empty, if it is occupied, or if someone is cage sitting.
	Note - the bot detects cage sitting by determining if the
	person in the cage adventures again in Hobopolis. So, the bot
	will not be able to tell if someone has stopped cagesitting if
	they stop adventuring in Hobopolis.
	(No options)
	
cwbot.modules.hobopolis.ExposureModule - Tracks the progress in
	Exposure Esplanade. EE is not well spaded, so the bot uses
	a linear approximation. Users can type "!ee" or "!exposure"
	to dispay the percent completion of EE.
	(No options)
	
cwbot.modules.hobopolis.HeapModule - Tracks the progress in the
	Heap. Specifically, this module tracks the stench level of the
	Heap, and when the I Refuse adventure is open, and how many
	players it can support. Players can type "!heap" to get
	this information.
	(No options)
	
cwbot.modules.hobopolis.HoboChatMonitorModule - This is an admin
	module that makes sure that players in Hobopolis are also
	listening to the /hobopolis chat channel. If a player is
	detected adventuring in Hobopolis, they are (silently) issued
	a strike. After a minute, if they adventure there again
	without signing into chat, they get another strike. If
	a player gets too many strikes, they are added to a violators
	list. At rollover, a list of violators is dispatched via kmail to any
	user with the "hobo_mon_daily" permission, and the list is cleared,
    but ONLY if at least one kmail was successfuly sent.
	Users with appropriate permissions can also use the "!chatmonitor" 
	command to see who received a violation, and "!chatmonitor dispatch" 
	to receive a kmail with violators, and "!chatmonitor clear" to clear the 
	list of violators.
	Note that it's possible to use a different permission than hobo_chat_mon
	for this module. If that is the case, then anyone with hobo_chat_mon
	permissions will get the daily kmail, and anyone with the permission
	for this module can use !chatmonitor commands. This is useful
	if someone is an administrator but does not want daily kmails.
	Options: num_warnings: number of warnings a player can receive before
				           being in violation (4)
             monitor_interval: how often to check for users in chat,
							   in seconds (55)
	
cwbot.modules.hobopolis.PldModule - Tracks the progress in the
	Purple Light District. Specifically, this module tracks the state of the
	club (i.e., whether it is opened or closed). Users can use "!pld" to check
	the status of the club.
	(No options)
	
cwbot.modules.hobopolis.SewerModule - Tracks the progress in the Sewers. 
	Specifically, this module tracks how many grates and valves have
	been opened. Players can use "!sewer" to see the status.
	(No options)
	
cwbot.modules.hobopolis.TownModule - The heart of Hobopolis monitoring.
	The town module has three responsibilities: it tracks the progress of
	the town square, it announces when new side areas or the tent have opened,
	and it coordinates data from other Hobopolis modules to get the overall
	status of the Hobopolis instance. As such, this module depends on
	several other modules - the following modules must be loaded and have
	a HIGHER priority than the TownModule: SewerModule, CageModule,
	BurnbarrelModule, ExposureModule, HeapModule, PldModule, AhbgModule,
	TownScarehoboModule, TownStageModule. If these modules are not loaded
	before the TownModule, the module will not function properly and
	probably crash.
	
	The TownModule will announce new side zone openings. However, since
	the bot cannot venture into Hobopolis, these opening messges are not
	exact -- the bot uses information from the logs and scarehobo creation
	to guess when zones are open. Since scarehobo damage has a random
	component, it is important to realize that the bot is approximate in
	this regard. In the same vein, the TownModule will announce when the
	tent has reopened -- but with the same caveat of imprecision.
	
	The TownModule will also announce when scarehobos have been built by
	monitoring the scarehobo stocks. It can't tell who built them, however.
	
	Two commands are available. The "!town" command will show the percent
	completion of the town, as well as the state of the stage. If the stage
	is open, it will say how many players are on stage. If closed, it will
	give an approximate count of hobo fights required until it opens again.
	This command also shows the number of scarehobos available for creation.
	
	The "!summary" (also "!hobopolis" or "!status") shows a general overview
	of Hobopolis completion, including which zones are open, which zones
	are complete, the percent completion of each zone, and the state
	of the C.H.U.M. cage.
	
	(No options)
	
cwbot.modules.hobopolis.TownScarehoboModule - This module is used by
	the TownModule to track scarehobo creation. It does not offer any
	direct contol, but must be loaded before the TownModule.
	(No options)
	
cwbot.modules.hobopolis.TownStageModule - This module is used by
	the TownModule to track the state of the tent. It does not offer any
	direct contol, but must be loaded before the TownModule.
	(No options)

cwbot.modules.hobopolis.TurnsModule - This module tracks the total number
	of turns in the Hobopolis instance. Use "!turns" to see a total turn
	count.
	(No options)
	



4. Contact Info
---------------

For more information, kmail RLBond86. If you like the bot, please donate some
Mr. As in appreciation.
