#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""High-level classes that coordinates various Downloaders, Parsers
and Generators (Renderers?) to create the static HTML files and other stuff"""

import os,sys
import inspect
from time import time
# my libs
from DispatchMixin import DispatchMixin

#class ParseManager:
    #"""Given a directory prepared by a Downlader, iterates and calls
    #the appropriate Parser for each downloaded LegalSource"""
    #def __init__(self,dir,parserClass,baseDir):
        #self.indexTree = ET.ElementTree(file=dir+"/index.xml")
        #for node in self.indexTree.getroot():
            #parser = parserClass(node.get("id"), dir + "/" + node.get("localFile"),baseDir)
            #parser.parse()

class Manager:
    def __init__(self,baseDir):
        self.baseDir = baseDir
    
    def _pairListToDict(self,pairlist):
        """maybe this could be done w/ list comprehensions (can they
        return an dict?)"""
        a = {}
        for p in pairlist:
            a[p[0]] = p[1]
        return a
    
    def _findModules(self):
        res = {}
        for f in [f for f in os.listdir(".") if f.endswith(".py") and f != "sitecustomize.py"]:
            modulename = inspect.getmodulename(f)
            # print "importing %s from %s" % (modulename,f)
            m = __import__(modulename,globals(),locals(),[])
            c = self._findManager(m)
            if c:
                if '__shortdesc__' in dir(m):
                    res[modulename] = m.__shortdesc__
                else:
                    res[modulename] = '<no description>'
        return res
    
    def _findManager(self,module):
        if module.__name__ == u'LegalSource':
            return # specialcase: LegalSource has a LegalSource.Manager class, but should not be directly instansiated
        import LegalSource
        classes = self._pairListToDict(inspect.getmembers(module,inspect.isclass))
        for classname in classes.keys():
            if LegalSource.Manager in inspect.getmro(classes[classname]):
                return classes[classname]

    def _doAction(self,action,module):
        if module == 'all':
            modules = self._findModules().keys()
        else:
            modules = (module,)
        for m in modules:
            start = time()
            mod = __import__(m, globals(), locals(), [])
            mgrClass = self._findManager(mod)
            if mgrClass:
                if hasattr(mod,'__moduledir__'):
                    mgr = mgrClass(self.baseDir, mod.__moduledir__)
                else:
                    mgr = mgrClass(self.baseDir)                
                if hasattr(mgr,action):
                    print "%s: calling %s" % (m,action)
                    method = getattr(mgr,action)
                    method()
                else:
                    print "Module %s's manager has no %s action" % (m,action)
            else:
                print "Module %s has no Manager class" % m
            print "%s: %s finished in %s seconds" % (m,action,time()-start)
            
    ACTIONS = {'download': 'download everything',
               'update'  : 'download updates',
               'parse'   : 'parse all downloaded (generate XML)',
               'index'   : 'create initial data about documents',
               'generate': 'generate HTML and create data about relations',
               'loaddb'  : 'refresh DB content',
               'test'    : 'do internal regression tests',
               'all'     : 'do everything in a sensible order'}
    
    def PrintUsage(self):
        print "Syntax: %s [action] [module]"
        print "action can be one of:"
        for a in ACTIONS.keys():
            print "  * %s: %s" % (a,ACTIONS[a])
        print "modules can be one of:"
        modules = self._findModules()
        for m in modules.keys():
            print "  * %s: %s" % (m,modules[m])
        print "  or `all' to do it to all modules"

    def ParseAll(self,module):
        self._doAction('ParseAll',module)

    def IndexAll(self,module):
        self._doAction('IndexAll',module)

    def GenerateAll(self,module):
        self._doAction('GenerateAll',module)
    
    def RelateAll(self,module):
        self._doAction('RelateAll',module)

    def Publish(self, module):
        self._doAction('Publish',module)
    
    def DoAll(self,module):
        start = time()
        self._doAction('ParseAll',module)
        self._doAction('IndexAll',module)
        self._doAction('GenerateAll',module)
        self._doAction('RelateAll',module)
        print "DoAll finished in %s seconds" % time() - start

if __name__ == "__main__":
    Manager.__bases__ += (DispatchMixin,)
    mgr = Manager('testdata')
    mgr.Dispatch(sys.argv)
