Description:
============

This is a collection of python scripts and modules, XSLT stylesheets
and various other pieces which is used to create all the static
content for https://lagen.nu/

Requirements:
=============

The code has been tested on windows and linux, and should run on
macosx and other unices as well, as long as the following requirements
are met (all command line programs must be in your PATH):

 * Python 2.5 together with

   * beautifulsoup
   * mechanize
   * configobj
   * simpleparse
   * rdflib 2.4
   * pyRDFa

 * xmllint and xsltproc (for XSLT transformations)
 * patch, find and recode (If you're on windows, install cygwin)
 * apache2 (to view the entire generated site -- if you're on windows
   you must use the cygwin version, since the win32 version has `a bug
   <https://issues.apache.org/bugzilla/show_bug.cgi?id=41441>`_
   concerning colons in URLs, which we use)
 
The required python modules should be installable with ``easy_install
beautifulsoup mechanize configobj simpleparse
"rdflib>=2.4,<=3.0a"``. PyRDFa isn't installable through easy_install,
you'll have to manually download it from from
http://www.w3.org/2007/08/pyRdfa/. Currently, there's a bug in that
module; you'll need to apply the following patch::

    --- pyRdfa/__init__.py  2008-08-16 23:38:58.043000000 +0200
    +++ pyRdfa/__init__.py~ 2008-06-16 12:23:42.000000000 +0200
    @@ -458,6 +458,6 @@
                    for t in options.warning_graph : graph.add(t)
    
            # That is it...
    -       return graph
    +       return Graph


For downloading verdicts from Domstolsverkets ftp-server and
transforming them into HTML you need four additional things:

 * A username/password - I can't give out mine, unfortunately
 * ncftp
 * pywin32 (python module)
 * Microsoft Word 2003 (possibly earlier and later versions work, but
   I haven't tested this)

If you can't get these, an easier way is to just download the
downloaded and converted documents from
http://ferenda.lagen.nu/dv.html.zip and unzip into
$WORKDIR/data/dv/intermediate (see more below)

Running:
========

The python scripts and modules are not meant to be installed in your
site-packages -- run them from your checked-out copy of the code.

The main executable module is ``Manager.py``, which takes a command
name parameter and, depending on the command, additional
parameters. Try running the regression test suite to see if things
seem OK:

``python Manager.py RunTest``

It should report some failures, but most test cases should work.

More Information:
=================

See the development trac (in Swedish) at http://trac.lagen.nu/


