# load a list of wanted texts
# - syntax for expressing just part of a text needed (http://www.lagen.nu/1962:700#K20 ? )
# 
# create one big xht2 file with all lawtext and other stuff
# - load in each file (optionally filtering out the needed part(s)
# - transform each file including metadata (particularly title) into a body-level section
# - maybe create a toc as well ?
#
# run prince on the result
#
# folkets jubel!
import sys,os
from SFS import SFSManager
from Util import mkdir as mkdirp
import xml.etree.cElementTree as ET


def parseList(s):
    return [l.strip().split("#") for l in s.split("\n")]

if __name__ == "__main__":
    m = SFSManager('testdata','sfs')
    for l in parseList(open(sys.argv[1]).read()):
        if ":" in l[0]:
            basefile = l[0].replace(":", "/")
            sys.stdout.write("doing %s\n" % basefile)
            m.Parse(basefile)
            # infile = "testdata/sfs/parsed/%s.xht2" % basefile # SFSManager should be able to tell me this
            # outfile = "testdata/sfs/pdf/%s.pdf" % basefile
            # mkdirp(os.path.dirname(outfile))
            # cmd = '"C:\\Program Files\\Prince\\Engine\\bin\\prince.exe" -s css\\print.css %s -o %s' % (infile, outfile)
            # sys.stdout.write("Generating: %s\n" % cmd)
            # os.system(cmd)
    # note that prince.exe has internal xinclude support, so this step isn't really needed
    # (is useful for debugging though)
    cmd = "xmllint --xinclude --format %s > out.xht2"  % sys.argv[2]
    os.system(cmd)
    cmd = '"C:\\Program Files\\Prince\\Engine\\bin\\prince.exe" -s css\\print.css out.xht2 -o out.pdf'
    os.system(cmd)
    

    

