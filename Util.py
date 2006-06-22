#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""General library of small utility functions"""
import os
import subprocess

class ValidationError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class TransformError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# FIXME: rewrite this to inherit the built-in dict object
class OrderedDict:
    """A combination of a list and a dictionary. There probably exists
    a much-better built-in version somewhere"""
    
    def __init__(self):
        self.list = []
        self.dict = {}

    def append(self,key,value):
        self.list.append([key,value])
        self.dict[key] = self.list[-1]

    def append_to_value(self,key,value):
        #print "append_to_value: initial value: '%s'" % self.dict[key][1]
        #print "append_to_value: value to append: '%s'" % value
        l = self.dict[key]
        l[1] += value
        #print "append_to_value: final value: '%s'" % self.dict[key][1]
        
    def item(self,key):
        return self.dict[key][1]

    def has_key(self,key):
        return self.dict.has_key(key)

    def extend(self,dict2):
        for item in dict2.list:
            self.list.append(item)


# FIXME: need to rewrite this
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

# FIXME: need to rewrite this
# from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/135435
def numsort(alist):
    """
    Sorts a list in numeric order. For example:
        ['aaa35', 'aaa6', 'aaa261'] 
    is sorted into:
        ['aaa6', 'aaa35', 'aaa261']
    """

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
    indices = map(_generate_index, alist)
    decorated = zip(indices, alist)
    decorated.sort()
    return [ item for index, item in decorated ]

def indentXmlFile(filename):
    """Neatifies an existing XML file in-place by running xmllint --format"""
    (ret,stdout,stderr) = runcmd("xmllint --format %s > tmp.xml" % filename)
    os.remove(filename)
    os.rename("tmp.xml",filename)

def tidyHtmlFile(filename):    
    """Neatifies an existing XHTML file in-place by running tidy"""
    if os.sys.platform == "darwin":
        tidycmd = "/usr/local/bin/tidy"
    else:
        tidycmd = "tidy"
    (ret,stdout,stderr) = runcmd("%s -q -n -i -asxhtml -latin1 -w 120 --doctype strict %s > tmp.xml" % (tidycmd,filename))
    # tidy always exists with a non-0 return code if there were any
    # hrefs with spaces in them, so let's just silently ignore errors
    # for now
    #if (ret != 0):
    #    raise TidyError(stderr)
    
    # os.system("xmllint --format %s > tmp.xml" % filename)
    os.remove(filename)
    os.rename("tmp.xml",filename)

def transform(stylesheet,infile,outfile,parameters={},validate=True):
    """Does a XSLT transform with the selected stylesheet. Afterwards, tidies the resulting HTML tree and validates it"""
    param_str = ""
    for p in parameters.keys():
        # this double style quoting is needed for lawlist.xsl when
        # using the tagname parameter on macos. Maybe for other
        # reasons as well, I dunno
        param_str += "--param %s \"'%s'\" " % (p,parameters[p])
    
    cmdline = "xsltproc %s %s %s > %s" % (param_str,stylesheet,infile,outfile)
    # print cmdline
    (ret,stdout,stderr) = runcmd(cmdline)
    if (ret != 0):
        raise TransformError(stderr)

    # can't use tidy for HTML fragments -- it creates <head> and <body> sections and other stuff
    # tidyHtmlFile(outfile)
    indentXmlFile(outfile)

    if validate:
        cmdline = "xmllint --noout --nonet --nowarning --dtdvalid %s/dtd/xhtml1-strict.dtd %s" % (basepath,outfile)
        (ret,stdout,stderr) = runcmd(cmdline)
        if (ret != 0):
            raise ValidationError(stderr)

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

def normalizeSpace(string):
    return " ".join(string.split())
