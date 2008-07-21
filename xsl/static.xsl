<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:dct="http://dublincore.org/documents/dcmi-terms/">

  <xsl:import href="uri.xsl"/>
  <xsl:include href="base.xsl"/>

  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    Statisk sida | Lagen.nu
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="headmetadata"/>
      
  <xsl:template match="/">
    <div class="middle">
      <xsl:apply-templates/>
    </div>  
  </xsl:template>

  <xsl:template match="xht2:h">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="xht2:a">
    <xsl:call-template name="uri"/>
  </xsl:template>
  <!-- specialregler som kopierar innehåll från xht2-namepace till
       xhtml1-dito. BORDE inte behövas med defaultregeln nedan, men
       tydligen (pga de namespaceprefix som ElementTree genererar) -
       känns som xsltproc beter sig skumt... -->
  <xsl:template match="xht2:ul">
    <ul><xsl:apply-templates/></ul>
  </xsl:template>
  <xsl:template match="xht2:li">
    <li><xsl:apply-templates/></li>
  </xsl:template>
  <xsl:template match="xht2:div">
    <div><xsl:apply-templates/></div>
  </xsl:template>
  
  <!-- defaultregel: kopierar alla element från xht2 till
       default-namespacet -->
  <xsl:template match="xht2:*">
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@xht2:*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

  <!-- refs mode -->

  <xsl:template match="*|@*" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  
</xsl:stylesheet>

