<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		>

  <xsl:import href="uri.xsl"/>
  <xsl:include href="base1.xsl"/>

  <xsl:template match="html">
    <not_really_html about="awesome">
      <xsl:apply-templates/>
    </not_really_html>
  </xsl:template>
  

  
  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//title"/> | Lagen.nu
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="headmetadata"/>
      
  <xsl:template match="h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="a">
    <xsl:call-template name="link"/>
  </xsl:template>

  <xsl:template match="body">
    <!-- should maybe be dct:title, not dct:identifier? -->
    <h1><xsl:value-of select="//*[@property='dct:identifier']"/></h1>
    <!-- should maybe be dct:description -->
    <h2><xsl:value-of select="//*[@property='dct:title']"/></h2>
    <xsl:apply-templates/>
  </xsl:template>

  <!-- defaultregel: Identity transform -->
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  
  <!-- refs mode -->
  <xsl:template match="h" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

 <xsl:template match="dl[@role='contentinfo']" mode="refs">
    <div class="sidoruta">
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <xsl:template match="*|@*" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <!-- kommentar mode -->
  <xsl:template match="*|@*" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>

  
</xsl:stylesheet>

