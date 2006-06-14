<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output encoding="iso-8859-1"
  	    method="xml"
  	    doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
  	    doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
  	    />
  
  <xsl:template match="/">
    <html>
    <head>
      <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
      <title><xsl:call-template name="headtitle"/></title>
      <xsl:call-template name="metarobots"/>
      <script type="text/javascript" src="/stuff.js"></script>
      <link rel="stylesheet" type="text/css" href="/default.css"/>
      <link rel="stylesheet" type="text/css" media="print" href="/print.css"/>
      <xsl:call-template name="linkrss"/>
      <xsl:call-template name="linkalternate"/>
    </head>
    <body onload="InitDisclaimer()">
      <form method="get" action="http://www.google.com/custom" style="display:inline;">
      <div class="navigation">
        <a href="/">Lagen.nu</a> -
        <a href="/nyheter">Nyheter</a> - 
        <a href="/index">Författningar</a> -
	<!--<a href="/index/domslut">Domslut</a> - -->
        <a href="/om">Om</a> -
        <span style="text-decoration: underline">S</span>ök:
        <!-- Search Google -->
        <input type="text" name="q" size="20" maxlength="255" value="" accesskey="S"/>
        <input type="hidden" name="cof" value="S:http://blog.tomtebo.org/;AH:center;AWFID:22ac01fa6655f6b6;"/>
        <input type="hidden" name="domains" value="lagen.nu"/><br/>
        <input type="hidden" name="sitesearch" value="lagen.nu" checked="checked"/>
        </div>
      </form>
      <xsl:apply-templates/>
    </body>
    </html>
  </xsl:template>
  
  <xsl:template name="htmltitle">
    Lagen.nu - Alla Sveriges lagar på webben
  </xsl:template>
  
  <xsl:template name="linkrss"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="metarobots"/>
  
</xsl:stylesheet>