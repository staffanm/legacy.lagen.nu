<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xhtml="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		xml:space="preserve"
		>
  <xsl:param name="infile">unknown-infile</xsl:param>
  <xsl:param name="outfile">unknown-outfile</xsl:param>
  <xsl:param name="annotationfile"/>

  <xsl:output method="xml"
  	    doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
  	    doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	    indent="yes"
	    />

  <xsl:template match="xhtml:head"><!--
 --><head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title><xsl:call-template name="headtitle"/></title>
    <script type="text/javascript" src="js/jquery-1.4.2.min.js"></script>
    <script type="text/javascript" src="js/jquery-ui-1.8.custom.min.js"></script>
    <script type="text/javascript" src="js/jquery.treeview.min.js"></script>
    <script type="text/javascript" src="js/base.js"></script>
    <link rel="shortcut icon" href="/img/favicon.ico" type="image/x-icon" />
    <link rel="stylesheet" href="css/reset.css" type="text/css"/> 
    <link rel="stylesheet" href="css/generic.css" type="text/css"/> 
    <link rel="stylesheet" href="css/jquery-ui-1.8.custom.css" type="text/css"/><!--
    --><xsl:call-template name="metarobots"/><!--
    --><xsl:call-template name="linkalternate"/><!--
    --><xsl:call-template name="headmetadata"/>
  </head><!--
--></xsl:template>

  <xsl:template match="xhtml:body">
    <body>
      <div id="header">
	<h1><a href="/">eurlex.lagen.nu</a></h1>
	<ul id="nav">
	  <li><a href="/primary" title="founding and amending treaties, protocols etc">Primary law</a></li>
	  <li><a href="/secondary" title="unilateral acts (regulations, directives, decisions, opinions and recommendations) and agreements">Secondary law</a></li>
	  <li><a href="/supplementary" title="the case law of the Court of Justice, international law and general principles of law.">Supplementary law</a></li>
	  <li><a href="/about">About</a></li>
	</ul>
	<form method="get" action="http://www.google.com/custom">
	  <p>
	    <input type="text" name="q" id="q" size="40"/>
	    <input type="submit" value="Search"/>
	  </p>
	</form>
      </div>
      <div id="toc">
	<ul>
	  <xsl:apply-templates mode="toc"/>
	</ul>
      </div>

      <div id="main">
	<p class="screenonly">Screen version</p>
	<p class="printonly">Print version</p>
	<p class="handheldonly">Mobile version</p>
	<xsl:apply-templates/>
      </div>

      <div id="footer">
	Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nunc
	vehicula metus ac urna ultrices varius. Cras at elit in orci
	semper semper. Mauris venenatis lectus at dolor feugiat varius
	dignissim lorem ullamcorper.
      </div>
    </body>
  </xsl:template>
</xsl:stylesheet>
