#!/sw/bin/python
# -*- coding: iso-8859-1 -*-
"""High-level classes that coordinates various Downloaders, Parsers
and Renderers to create the static HTML files and other stuff"""

import os,sys
import inspect

class ParseManager:
    """Given a directory prepared by a Downlader, iterates and calls
    the appropriate Parser for each downloaded LegalSource"""
    def __init__(self,dir,parserClass,baseDir):
        self.indexTree = ET.ElementTree(file=dir+"/index.xml")
        for node in self.indexTree.getroot():
            parser = parserClass(node.get("id"), dir + "/" + node.get("localFile"),baseDir)
            parser.parse()


def pairlist_to_assoc(pairlist):
    """maybe this could be done w/ list comprehensions (can they
    return an associative array?)"""
    a = {}
    for p in pairlist:
        a[p[0]] = p[1]
    return a

def find_modules():
    res = {}
    for f in [f for f in os.listdir(".") if f.endswith(".py") and f != "sitecustomize.py"]:
        modulename = inspect.getmodulename(f)
        # print "importing %s from %s" % (modulename,f)
        m = __import__(modulename,globals(),locals(),[])
        c = find_manager(m)
        if c:
            if '__shortdesc__' in dir(m):
                res[modulename] = m.__shortdesc__
            else:
                res[modulename] = '<no description>'
    return res

def find_manager(module):
    import LegalSource
    classes = pairlist_to_assoc(inspect.getmembers(module,inspect.isclass))
    for classname in classes.keys():
        if LegalSource.Manager in inspect.getmro(classes[classname]):
            return classes[classname]
    
ACTIONS = {'download': 'download everything',
           'update'  : 'download updates',
           'parse'   : 'parse all downloaded (generate XML)',
           'generate': 'generate HTML',
           'loaddb'  : 'refresh DB content',
           'test'    : 'do internal regression tests',
           'all'     : 'do everything in a sensible order'}

def print_usage():
    print "Syntax: %s [action] [module]"
    print "action can be one of:"
    for a in ACTIONS.keys():
        print "  * %s: %s" % (a,ACTIONS[a])
    print "modules can be one of:"
    modules = find_modules()
    for m in modules.keys():
        print "  * %s: %s" % (m,modules[m])
    print "  or `all' to do it to all modules"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
    else:
        # fixme: ensure action/module are valid
        action = sys.argv[1]
        module = sys.argv[2]
        
        # try to load the module
        mod = __import__(module, globals(), locals(), [])
        if action == 'parse':
            mgrClass = find_manager(mod)
            mgr = mgrClass("testdata")
            mgr.parseAll()
