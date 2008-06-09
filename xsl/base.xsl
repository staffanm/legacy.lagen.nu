<?xml version="1.0" encoding="ISO-8859-1"?>
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
      <link rel="shortcut icon" href="http://lagen.nu/favicon.ico" type="image/x-icon" />
      <link rel="stylesheet" type="text/css" href="file:///home/staffan/wds/svn.lagen.nu/css/default.css"/>
      <xsl:call-template name="linkalternate"/>
      <xsl:call-template name="headmetadata"/>
    </head>
  </xsl:template>

  <xsl:template match="xht2:body">
    <!--<xsl:message>base/body</xsl:message>-->
    <body>
      <div id="vinjett">
	<form method="get" action="http://www.google.com/custom" style="display:inline;">
	  <div class="navigation">
	    <a href="/">Lagen.nu</a> -
	    <a href="/nyheter">Nyheter</a> - 
	    <a href="/index/sfs">Författningar</a> -
	    <a href="/index/dv">Domslut</a> -
	    <a href="/om">Om</a> -
	    <u>S</u>ök:
	    <input type="text" name="q" size="20" maxlength="255" value="" accesskey="S"/>
	    <input type="hidden" name="cof" value="S:http://blog.tomtebo.org/;AH:center;AWFID:22ac01fa6655f6b6;"/>
	    <input type="hidden" name="domains" value="lagen.nu"/><br/>
	    <input type="hidden" name="sitesearch" value="lagen.nu" checked="checked"/>
	  </div>
	</form>
      </div>
      <div id="wrapper_extra">
	<div id="wrapper">
	  <div id="lagtext">
	    <xsl:apply-templates/>
	  </div>
	  <div id="kommentarer">
	    <div class="sidoruta">
	      &#160;
	    </div>
	  </div>
	  <div id="referenser">
	    <div class="sidoruta">
	      <p>Om dokumentet</p>
	      <xsl:apply-templates mode="refs"/>
	    </div>
	  </div>
	</div>
	<div id="sidfot">
	  <b>Lagen.nu:</b> Mauris non risus a nisi posuere
	  gravida. Morbi ut lacus. Nulla faucibus pulvinar ligula. Proin
	  mattis. Maecenas sagittis venenatis lorem. Praesent facilisis
	  posuere pede.
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