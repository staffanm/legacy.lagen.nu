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
    <xsl:value-of select="//xht2:title"/> | Lagen.nu
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
    <xsl:call-template name="link"/>
  </xsl:template>
  <!-- specialregler som kopierar innehåll från xht2-namepace till
       xhtml1-dito. BORDE inte behövas med defaultregeln nedan, men
       tydligen (pga att ElementTree genererar ns0 som namespaceprefix
       istf xht2 som detta stylesheet använder) - känns som xsltproc
       beter sig skumt... -->
  <xsl:template match="xht2:ul">
    <ul><xsl:apply-templates/></ul>
  </xsl:template>
  <xsl:template match="xht2:li">
    <li><xsl:apply-templates/></li>
  </xsl:template>
  <xsl:template match="xht2:div">
    <div><xsl:apply-templates/></div>
  </xsl:template>
  <xsl:template match="xht2:p">
    <p><xsl:apply-templates/></p>
  </xsl:template>

  <xsl:template match="xht2:p[@role='secondary']">
    <!-- emit nothing -->
  </xsl:template>
  
  <!-- defaultregel: kopierar alla element från xht2 till
       default-namespacet -->
  <xsl:template match="xht2:*">
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="xht2:*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

  <!-- refs mode -->

  <xsl:template match="*|@*" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <!-- kommentarer mode -->

  <xsl:template match="xht2:div" mode="kommentarer">
    <xsl:apply-templates select="//xht2:p[@role='secondary']" mode="trans-ns"/>
  </xsl:template>

  <xsl:template match="*" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>

  
  <!-- generic namespace translation -->
  <xsl:template match="xht2:div" mode="trans-ns">
    <div><xsl:apply-templates mode="trans-ns"/></div>
  </xsl:template>
  <xsl:template match="xht2:span" mode="trans-ns">
    <span><xsl:apply-templates mode="trans-ns"/></span>
  </xsl:template>
  <xsl:template match="xht2:p" mode="trans-ns">
    <p><xsl:apply-templates mode="trans-ns"/></p>
  </xsl:template>
  
  
  
</xsl:stylesheet>

