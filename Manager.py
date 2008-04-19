#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""High-level classes that coordinates various Downloaders, Parsers
and Generators (Renderers?) to create the static HTML files and other stuff"""

import os,sys
import inspect
import time
import logging
# my libs
from DispatchMixin import DispatchMixin
import LegalSource

log = logging.getLogger('manager')

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
            if (LegalSource.Manager in inspect.getmro(classes[classname])
                and str(classes[classname]).startswith(module.__name__)):
                return classes[classname]

    def _doAction(self,action,module):
        if module == 'all':
            modules = self._findModules().keys()
        else:
            modules = (module,)
        for m in modules:
            # print "doing %s" % m
            start = time.time()
            mod = __import__(m, globals(), locals(), [])
            mgrClass = self._findManager(mod)
            if mgrClass:
                if hasattr(mod,'__moduledir__'):
                    mgr = mgrClass(self.baseDir, mod.__moduledir__)
                else:
                    mgr = mgrClass(self.baseDir)                
                if hasattr(mgr,action):
                    log.info(u'%s: calling %s' % (m,action))
                    method = getattr(mgr,action)
                    method()
                else:
                    print "Module %s's manager has no %s action" % (m,action)
            else:
                print "Module %s has no Manager class" % m
            log.info(u'%s: %s finished in %s seconds' % (m,action,time.strftime("%H:%M:%S", time.gmtime(time.time()-start))))
            
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
        for a in self.ACTIONS.keys():
            print "  * %s: %s" % (a,self.ACTIONS[a])
        print "modules can be one of:"
        modules = self._findModules()
        for m in modules.keys():
            print u"  * %r: %r" % (m,modules[m])
        print "  or `all' to do it to all modules"

    def DownloadAll(self, module):
        self._doAction('DownloadAll',module)

    def DownloadNew(self, module):
        self._doAction('DownloadNew', module)
        
    def ParseAll(self,module):
        self._doAction('ParseAll',module)

    def IndexAll(self,module):
        self._doAction('IndexAll',module)

    def GenerateAll(self,module):
        self._doAction('GenerateAll',module)
    
    def RelateAll(self,module):
        self._doAction('RelateAll',module)

    def GenerateSite(self):
        log.info("Creating some main html pages here")
    
    def Publish(self):
        cmd = "tar czf - %s | ssh staffan@vps.tomtebo.org \"cd /www/staffan/ferenda.lagen.nu && tar xvzf - && chmod -R go+r %s\"" % (self.baseDir, self.baseDir)
        #print "executing %s" % cmd
        #os.system(cmd)
        log.info("doing some scp:ing here")
    
    def DoAll(self,module):
        start = time.time()
        self._doAction('DownloadNew',module)
        self._doAction('ParseAll',module)
        # self._doAction('IndexAll',module)
        self._doAction('RelateAll',module)
        self._doAction('GenerateAll',module)
        self.GenerateSite()
        self.Publish()
        log.info(u'DoAll finished in %s seconds' % time.strftime("%H:%M:%S",time.gmtime(time.time() - start)))

if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('etc/log.conf')
    Manager.__bases__ += (DispatchMixin,)
    mgr = Manager('testdata')
    mgr.Dispatch(sys.argv)
