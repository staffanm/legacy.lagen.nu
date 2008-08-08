<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dc="http://purl.org/dc/elements/1.1/">
  <!-- fixme: change dc to dct -->

  <xsl:output method="xml"
  	    doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
  	    doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"  	    />
  
  <xsl:template match="/">
    <!--<xsl:message>Root rule</xsl:message>-->
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="xht2:html">
    <!--<xsl:message>base/root</xsl:message>-->
    <html><xsl:apply-templates/></html>
  </xsl:template>
    
  <xsl:template match="xht2:head">
    <!--<xsl:message>base/head</xsl:message>-->
    <head>
      <title><xsl:call-template name="headtitle"/></title>
      <xsl:call-template name="metarobots"/>
      <script type="text/javascript" src="base.js"></script>
      <link rel="shortcut icon" href="file:///C:/Users/staffan/wds/ferenda.lagen.nu/img/favicon.ico" type="image/x-icon" />
      <!-- <link rel="stylesheet" type="text/css" href="file:///home/staffan/wds/svn.lagen.nu/css/default.css"/> -->
      <link rel="stylesheet" type="text/css" href="file:///C:/Users/staffan/wds/ferenda.lagen.nu/css/default.css"/>
      
      <xsl:call-template name="linkalternate"/>
      <xsl:call-template name="headmetadata"/>
    </head>
  </xsl:template>

  <xsl:template match="xht2:body">
    <!--<xsl:message>base/body</xsl:message>-->
    <body>
      <div id="vinjett">
	<h1><a href="/">lagen.nu</a></h1>
	<ul id="navigation">
	  <li><a href="/nyheter">Nyheter</a></li>
	  <li><a href="/index/sfs">Författningar</a></li>
	  <li><a href="/index/dv">Domslut</a></li>
	  <li><a href="/om">Om</a></li>
	</ul>
	<form method="get" action="http://www.google.com/custom" style="display:inline;">
	  <u>S</u>ök:
	  <input type="text" name="q" size="20" maxlength="255" value="" accesskey="S"/>
	  <input type="hidden" name="cof" value="S:http://blog.tomtebo.org/;AH:center;AWFID:22ac01fa6655f6b6;"/>
	  <input type="hidden" name="domains" value="lagen.nu"/><br/>
	  <input type="hidden" name="sitesearch" value="lagen.nu" checked="checked"/>
	</form>
      </div>
      <div id="wrapper_extra">
	<div id="wrapper">
	  <div id="lagtext">
	    <xsl:apply-templates/>
	  </div>
	  <div id="kommentarer" class="sidoruta">
	    <xsl:apply-templates mode="kommentarer"/>
	  </div>
	  <div id="referenser" class="sidoruta">
	    <xsl:apply-templates mode="refs"/>
	  </div>
	</div>
	<div id="sidfot">
	  <b>Lagen.nu</b> är en privat webbplats. Informationen här är
	  inte officiell och kan innehålla fel.
	</div>
      </div>
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