#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import sys
import cPickle
from pprint import pprint
from time import time
# from SFS import SFSManager

if __name__ == "__main__":
    start = time()
    d = cPickle.load(file(sys.argv[1]))
    print "Loaded %s in %s" % (sys.argv[1],time()-start)
    
    # mgr = SFSManager('testdata','sfs')
    # d = mgr._referencesAsArray(sys.argv[1],'sfs')
    
    print pprint(d)

