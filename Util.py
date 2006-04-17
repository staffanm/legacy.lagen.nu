#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
"""General library of small utility functions"""

import os
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/82465
def mkdir(newdir):
    """works the way a good mkdir should :)
    - already exists, silently complete
    - regular file in the way, raise an exception
    - parent directory(ies) does not exist, make them as well
    """
    if os.path.isdir(newdir):
        pass
    elif os.path.isfile(newdir):
        raise OSError("a file with the same name as the desired " \
                      "dir, '%s', already exists." % newdir)
    else:
        head, tail = os.path.split(newdir)
        if head and not os.path.isdir(head):
            mkdir(head)
            #print "mkdir %s" % repr(newdir)
        if tail:
            os.mkdir(newdir)
                
