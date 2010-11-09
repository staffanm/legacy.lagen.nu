# Small utility script to speed up creations of patch files for legal documents

import sys,os
import codecs
from tempfile import mktemp
from shutil import copy2

import Util

if __name__ == "__main__":
    coding = 'utf-8' if sys.stdin.encoding == 'UTF-8' else 'iso-8859-1'
    myargs = [arg.decode(coding) for arg in sys.argv]

    # ask for description and place it alongside

    # copy the modified file to a safe place
    file_to_patch = myargs[1].replace("\\","/") # normalize
    tmpfile = mktemp()
    copy2(file_to_patch,tmpfile)
        
    # Run SFSParser._extractSFST() (and place the file in the correct location)
    # or DVParser.word_to_docbook() 
    if "/sfs/intermediate/" in file_to_patch:
        source = "sfs"
        basefile = file_to_patch.split("/sfs/intermediate/")[1]
        import SFS
        p = SFS.SFSParser()
        sourcefile = file_to_patch.replace("/intermediate/", "/downloaded/sfst/").replace(".txt", ".html")
        print "source %s, basefile %s, sourcefile %s" % (source,basefile,sourcefile)
        plaintext = p._extractSFST([sourcefile])
        f = codecs.open(file_to_patch, "w",'iso-8859-1')
        f.write(plaintext+"\n")
        f.close()
        print "Wrote %s bytes to %s" % (len(plaintext), file_to_patch)

    elif "/dv/intermediate/docbook/" in file_to_patch:
        source = "dv"
        basefile = file_to_patch.split("/dv/intermediate/docbook/")[1]
        import DV
        p = DV.DVParser()
        sourcefile = file_to_patch.replace("/docbook/", "/word/").replace(".xml", ".doc")
        print "source %r, basefile %r, sourcefile %r" % (source,basefile,sourcefile)
        os.remove(file_to_patch)
        p.word_to_docbook(sourcefile, file_to_patch)
        
    elif "/dv/intermediate/ooxml/" in file_to_patch:
        source = "dv"
        basefile = file_to_patch.split("/dv/intermediate/ooxml/")[1]
        import DV
        p = DV.DVParser()
        sourcefile = file_to_patch.replace("/ooxml/", "/word/").replace(".xml", ".docx")
        print "source %r, basefile %r, sourcefile %r" % (source,basefile,sourcefile)
        os.remove(file_to_patch)
        p.word_to_ooxml(sourcefile, file_to_patch)

    # calculate place in patch tree
    patchfile = "patches/%s/%s.patch" % (source, os.path.splitext(basefile)[0])
    Util.ensureDir(patchfile)
    
    # run diff on the original and the modified file, placing the patch right in the patch tree
    cmd = "diff -u %s %s > %s" % (file_to_patch, tmpfile, patchfile)
    print "Running %r" % cmd
    (ret, stdout, stderr) = Util.runcmd(cmd)

    if os.stat(patchfile).st_size == 0:
        print "FAIL: Patchfile is empty"
        os.remove(patchfile)
    else:
        if sys.platform == "win32":
            os.system("unix2dos %s" % patchfile)
        print "Created patch file %r" % patchfile
        print "Please give a description of the patch"
        patchdesc = sys.stdin.readline().decode('cp850')
        fp = codecs.open(patchfile.replace(".patch",".desc"),"w",'utf-8')
        fp.write(patchdesc)
        fp.close()

    
