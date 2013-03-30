def importClass(classFullName):
    s = classFullName.rsplit(".", 1)
    importPackage = s[0]
    className = s[-1]
    mod = __import__(importPackage, fromlist=[className])
    ModuleClass = getattr(mod, className)
    return ModuleClass


def _easyImport(baseName, className, useBase):
    
    classFullName = className
    if useBase:
        classFullName = baseName + "." + className
    
    # first: try Name1.Name2.Name3.Name3 (i.e., class matches filename)
    try:
        s = classFullName.rsplit(".", 1)
        className = s[-1]
        return importClass(classFullName + "." + className)
    except (ImportError, AttributeError):
        # failed
        pass

    # next: try Name1.Name2.Name3 (i.e., Name3 is classname)
    try:
        return importClass(classFullName)
    except (ImportError, AttributeError):
        # failed
        pass
    
    # finally: try again while ignoring the base name
    if useBase:
        return _easyImport(baseName, className, useBase=False)
    raise ImportError("No such module/class: {}".format(classFullName))


def easyImportClass(baseName, className):
    return _easyImport(baseName, className, useBase=True)
