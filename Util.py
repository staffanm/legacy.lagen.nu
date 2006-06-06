#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
"""General library of small utility functions"""
import os
import subprocess

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
                
# from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/135435
def numsort(alist):
    """
    Sorts a list in numeric order. For example:
        ['aaa35', 'aaa6', 'aaa261'] 
    is sorted into:
        ['aaa6', 'aaa35', 'aaa261']
    """
    indices = map(_generate_index, alist)
    decorated = zip(indices, alist)
    decorated.sort()
    return [ item for index, item in decorated ]

def _generate_index(str):
    """
    Splits a string into alpha and numeric elements, which
    is used as an index for sorting
    """
    #
    # the index is built progressively
    # using the _append function
    #
    index = []
    def _append(fragment, alist=index):
        if fragment.isdigit(): fragment = int(fragment)
        alist.append(fragment)

    # initialize loop
    prev_isdigit = str[0].isdigit()
    current_fragment = ''
    # group a string into digit and non-digit parts
    for char in str:
        curr_isdigit = char.isdigit()
        if curr_isdigit == prev_isdigit:
            current_fragment += char
        else:
            _append(current_fragment)
            current_fragment = char
            prev_isdigit = curr_isdigit
    _append(current_fragment)
    return tuple(index)


def indentXmlFile(filename):
    """Neatifies an existing XML file in-place by running xmllint --format"""
    (ret,stdout,stderr) = runcmd("xmllint --format %s > tmp.xml" % filename)
    os.remove(filename)
    os.rename("tmp.xml",filename)

def uniqueList(*lists):
    slots = {}
    for l in lists:
        for i in l:
            slots[i] = 1
    return slots.keys();

def runcmd(cmdline):
    # print "runcmd: %s" % cmdline
    p = subprocess.Popen(cmdline,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    stdout = p.stdout.read()
    stderr = p.stderr.read()
    ret = p.wait()
    return (ret,stdout,stderr)

