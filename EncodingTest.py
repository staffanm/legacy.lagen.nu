#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import sys,codecs

# initial state
sys.stdout.write(u"sys.getdefaultencoding():   %s\n" % sys.getdefaultencoding())
sys.stdout.write(u"sys.stdout.encoding:        %s\n" % sys.stdout.encoding)
sys.stdout.write(u"Performing codec/locale magic\n")
# deep codec/locale magic
import locale
locale.setlocale(locale.LC_ALL,'')
s = u"räksmörgås"
reload(sys)

if sys.stdout.encoding: # not set when stdout is redirected
    sys.setdefaultencoding(sys.stdout.encoding)
else:
    if sys.platform == 'win32':
        sys.setdefaultencoding('cp850')
    else:
        sys.setdefaultencoding('iso-8859-1') # a reasonable default?

sys.stdout = codecs.getwriter(sys.getdefaultencoding())(sys.__stdout__, 'replace')
sys.stderr = codecs.getwriter(sys.getdefaultencoding())(sys.__stderr__, 'replace')

        
sys.stdout.write(u"sys.getdefaultencoding():   %s\n" % sys.getdefaultencoding())
sys.stdout.write(u"sys.stdout.encoding:        %s\n" % sys.stdout.encoding)

sys.stdout.write(u"repr(teststring):           %r\n" % s)
sys.stdout.write(u"teststring.encode('cp850'): %s\n" % s.encode('cp850'))
sys.stdout.write(u"teststring:                 %s\n" % s)
sys.stdout.write(u"'å'.isalpha():              %s\n" % 'å'.isalpha())
sys.stdout.write(u"u'å'.isalpha():             %s\n" % u'å'.isalpha())

# a character not in either cp850 or latin-1 - if the codecs.getwriter
# magic worked, it should be replaced with '?'
sys.stdout.write(u"endash:                     %s\n" % u'\u2013')
