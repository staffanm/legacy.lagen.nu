<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dc="http://purl.org/dc/elements/1.1/">
		<!-- fixme: change dc to dct -->
  <xsl:template match="xht2:html">
    <html><xsl:apply-templates/></html>
  </xsl:template>  

  <xsl:template match="xht2:head">
    <head>
      <title>[lagnamn] ([alternativform]) | Lagen.nu</title>
      <link rel="shortcut icon" href="http://lagen.nu/favicon.ico" type="image/x-icon" />
      <link rel="stylesheet" type="text/css" href="file://C|/Users/staffan/wds/ferenda.lagen.nu/css/default.css" />
      <xsl:comment>all övrig metadata</xsl:comment>
    </head>
  </xsl:template>

  <xsl:template match="xht2:body">
    <body>
      <xsl:apply-templates/>
    </body>
  </xsl:template>

  <xsl:template match="xht2:h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div><xsl:apply-templates/></div>
  </xsl:template>
  
  <xsl:template match="*">
    <!-- xsl:copy är inte rätt - vi måste översätta från xht2 till
         xhtml-namespace på alla element -->
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

</xsl:stylesheet>