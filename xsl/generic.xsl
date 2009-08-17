<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		exclude-result-prefixes="xht2 rdf">

  <xsl:import href="uri.xsl"/>
  <xsl:include href="base.xsl"/>
  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//xht2:title"/> | Lagen.nu
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="headmetadata"/>
      
  <xsl:template match="xht2:h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="xht2:a">
    <xsl:call-template name="link"/>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="xht2:body">
    <!-- should maybe be dct:title, not dct:identifier? -->
    <h1><xsl:value-of select="../xht2:head/xht2:title"/></h1>
    <!-- should maybe be dct:description -->
    <h2><xsl:value-of select="//*[@property='dct:title']"/></h2>
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="xht2:dl[@role='contentinfo']"/>

  <!-- defaultregel: kopierar alla element från xht2 till
       default-namespacet -->
  <xsl:template match="*">
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

  <!-- refs mode -->
  <xsl:template match="xht2:h" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <xsl:template match="xht2:dl[@role='contentinfo']" mode="refs">
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

