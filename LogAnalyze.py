#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Går igenom en logg från en typisk körning och skapar HTML-filer om
vad som gått bra och dåligt (en övergripande vy och en sida per
modul/operation)"""

import re,sys,codecs,locale

locale.setlocale(locale.LC_ALL,'') 
if sys.platform == 'win32':
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        defaultencoding = 'cp850'
else:
    if sys.stdout.encoding:
        defaultencoding = sys.stdout.encoding
    else:
        defaultencoding = locale.getpreferredencoding()
# print "setting sys.stdout to a '%s' writer" % defaultencoding
sys.stdout = codecs.getwriter(defaultencoding)(sys.__stdout__, 'replace')
sys.stderr = codecs.getwriter(defaultencoding)(sys.__stderr__, 'replace')


re_logline = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) +\(([a-zA-Z0-9_, ]*)\) (\w+): ([^:]+)(: ([^\r]*)|)').match
re_tbframe = re.compile(r'  File "([^"]+)", line (\d+), in (\w+)').match
re_msg = re.compile(r'')
def analyse(logfile):
    f = codecs.open(logfile,encoding='utf-8')
    errcnt = 0
    warncnt = 0
    okcnt = 0
    errlocs = {}
    warnlocs = {}
    for line in f:
        log_match = re_logline(line)
        if not log_match:
            sys.stdout.write(u"Malformed log line: %r\n" % line)
        else:
            dt = log_match.group(1)
            module = log_match.group(2)
            loc = log_match.group(3)
            level = log_match.group(4)
            docid = log_match.group(5)
            message = log_match.group(7)
            if level == 'ERROR':
                errcnt += 1
                # print "ERR: %s" % message
                done = False
                while not done:
                    line = f.next()
                    if 'Error: ' in line:
                        done = True
                    # sys.stdout.write("    TB: " + line)
                    fb_match = re_tbframe(line)
                    if fb_match:
                        errloc = "%s:%s" % (fb_match.group(1), fb_match.group(2))
                    else:
                        errcode = line
                #errloc += "(%s)" % line.split(":")[0]
                errloc += "(%s)" % line[:-2]
                errlocs[errloc] = errlocs.get(errloc,0) + 1

            elif level == 'WARNING':
                warncnt += 1
                warnloc = "%s (%s)" % (loc,message)
                # print "WARNLOC %r" % warnloc
                warnlocs[warnloc] = warnlocs.get(warnloc,0) + 1
            elif level == 'INFO':
                if 'OK' in message:
                    okcnt += 1

    print "%s errors, %s warnings, %s ok" % (errcnt, warncnt, okcnt)
    print "ERRORS"
    printdict(errlocs)
    print "WARNINGS"
    printdict(warnlocs)

                 
def printdict(d):
    items = d.items()
    items = [(v, k) for (k, v) in items]
    items.sort()
    items.reverse()		# so largest is first
    items = [(k, v) for (v, k) in items]

    for k,v in items:
        print u"    %s: %s occurrences" % (k,v)
    

if __name__ == "__main__":
    analyse(sys.argv[1])
    
