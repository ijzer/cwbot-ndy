""" Modules are contained in this package. Modules are the lowest tier of
the three-tiered processing chain. Each module is "owned" by a manager, that
decides whether or not to invoke the module's processing abilities. 

A module does two things: first, it must decide if a chat or kmail is
applicable to its task. If it is not, it should return None from its processing
function. If it is, it must do the second thing: process the chat/kmail in
some meaningful way and do some action.

A good module should be focused on a single task, instead of being a
monolithic entity that performs many tasks. If one piece of processing needs
to be used by many other modules, you should use the Event subsystem to
communicate between each other. """