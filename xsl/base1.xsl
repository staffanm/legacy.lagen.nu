<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		>
  <xsl:param name="infile">unknown-infile</xsl:param>
  <xsl:param name="outfile">unknown-outfile</xsl:param>
  <xsl:param name="annotationfile"/>

  <xsl:output method="xml"
  	    doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
  	    doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	    indent="yes"
	    />

  <!-- these minimal RDF files is only used to know wheter we have a
       specific case (and therefore should link it) or keyword, so
       that we can know when to link to it -->
  <xsl:variable name="rattsfall" select="document('../data/dv/parsed/rdf-mini.xml')/rdf:RDF"/>
  <xsl:variable name="terms" select="document('../data/keyword/parsed/rdf-mini.xml')/rdf:RDF"/>
  <xsl:variable name="lagkommentar" select="document('../data/sfs/parsed/rdf-mini.xml')/rdf:RDF"/>
  <xsl:variable name="annotations" select="document($annotationfile)/rdf:RDF"/>

  <xsl:template match="/">
    <xsl:apply-templates/>
  </xsl:template>
  
  <xsl:template match="html">
    <html about="awesome">
      <xsl:apply-templates/>
    </html>
  </xsl:template>
  
  <xsl:template match="head">
    <head>
      <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
      <title><xsl:call-template name="headtitle"/></title>
      <xsl:call-template name="metarobots"/>
      <script type="text/javascript" src="/js/jquery-1.3.2.min.js"></script>
      <script type="text/javascript" src="/js/jquery-ui-1.7.2.custom.min.js"></script>
      <script type="text/javascript" src="/js/jquery.treeview.min.js"></script>
      <script type="text/javascript" src="/js/base.js"></script>
      <link rel="shortcut icon" href="/img/favicon.ico" type="image/x-icon" />
      <link rel="stylesheet" href="/css/screen.css" media="screen" type="text/css"/> 
      <link rel="stylesheet" href="/css/print.css" media="print" type="text/css"/>
      <link rel="stylesheet" href="/css/jquery-ui-1.7.2.custom.css" type="text/css"/> 
      <xsl:call-template name="linkalternate"/>
      <xsl:call-template name="headmetadata"/>
    </head>
  </xsl:template>

  <xsl:template match="body">
    <body>
      <xsl:if test="//html/@about">
	<xsl:attribute name="about"><xsl:value-of select="//html/@about"/></xsl:attribute>
      </xsl:if>

      <xsl:attribute name="typeof"><xsl:value-of select="@typeof"/></xsl:attribute>
      <div id="vinjett">
	<!-- <img src="/img/blueprint.jpg" alt=""/> -->
	<h1><a href="/">lagen.nu</a></h1>
	<ul id="navigation">
	  <li><a href="/nyheter/">Nyheter</a></li>
	  <li><a href="/index/">Lagar</a></li>
	  <li><a href="/dom/index/">Domar</a></li>
	  <li><a href="/begrepp/index/">Begrepp</a></li>
	  <li><a href="/om/">Om</a></li>
	</ul>
	<form method="get" action="http://www.google.com/custom">
	  <p>
	    <input type="text" name="q" id="q" size="40" maxlength="255" value="" accesskey="S"/>
	    <input type="hidden" name="cof" value="S:http://blog.tomtebo.org/;AH:center;AWFID:22ac01fa6655f6b6;"/>
	    <input type="hidden" name="domains" value="lagen.nu"/>
	    <input type="hidden" name="sitesearch" value="lagen.nu" checked="checked"/>
	    <input type="submit" value="Sök"/>
	  </p>

	</form>
      </div>
      <div id="innehallsforteckning">
	<ul id="toc">
	  <xsl:apply-templates mode="toc"/>
	</ul>
      </div>

      <div id="dokument">
	<xsl:apply-templates/>
      </div>

      <div id="sidfot">
	<b>Lagen.nu</b> är en privat webbplats. Informationen här är
v	inte officiell och kan vara felaktig | <a href="/om/ansvarsfriskrivning.html">Ansvarsfriskrivning</a> | <a href="/om/kontakt.html">Kontaktinformation</a>
      </div>
      <script type="text/javascript"><xsl:comment>
var gaJsHost = (("https:" == document.location.protocol) ? "https://ssl." : "http://www.");
document.write(unescape("%3Cscript src='" + gaJsHost + "google-analytics.com/ga.js' type='text/javascript'%3E%3C/script%3E"));
      </xsl:comment></script>
      <script type="text/javascript"><xsl:comment>
var pageTracker = _gat._getTracker("UA-172287-1");
pageTracker._trackPageview();
      </xsl:comment></script>
    </body>
  </xsl:template>

  <!-- defaultimplementationer av de templates som anropas -->
  <!--
  <xsl:template name="headtitle">
    Lagen.nu - Alla Sveriges lagar på webben
  </xsl:template>
  <xsl:template name="linkrss"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="metarobots"/>
  <xsl:template name="headmetadata"/>
  -->
  
</xsl:stylesheet>
