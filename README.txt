REQUIREMENTS:

(easy_install) beautifulsoup mechanize configobj simpleparse
"rdflib>=2.4,<=3.0a", mySQL-python

Also, pyRDFa from http://www.w3.org/2007/08/pyRdfa/ -- needs patch:

	return graph

instead of

	return Graph

on the very last line of __init__.py

To run DV.py DownloadNew you need ncftp et al in your PATH

To run DV.py ParseAll you need Windows and Microsoft Word installed

RUNNING:

The system needs a running MYSQL database for storing RDF triples.

    mysqladmin -u root create rdfstore
    mysql -u root rdfstore
    mysql> GRANT all ON rdfstore TO 'rdflib' IDENTIFIED BY 'rdflib';

Then run:

     python Manager.py InitializeDB

HACKING:
