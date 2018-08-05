<?xml version="1.0" encoding="utf-8"?>
<!-- note: this is a XHTML1 template -->
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xhtml="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#"
		xmlns:rinfoex="http://lagen.nu/terms#"
		exclude-result-prefixes="xhtml rdf">

  <xsl:import href="uri1.xsl"/>
  <xsl:include href="base1.xsl"/>

  
  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//xhtml:title"/> | Lagen.nu<!-- -->
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="headmetadata"/>
  <xsl:template name="banner">
    <div class="banner">Ny version av lagen.nu tillgänglig -- <a href="http://ferenda.lagen.nu/">klicka här</a> för att testa!</div>
  </xsl:template>
      

  <xsl:template match="xhtml:a">
    <xsl:call-template name="link"/>
  </xsl:template>

  <xsl:template match="*[@typeof='eurlex:Article']">
    <xsl:variable name="uri" select="@about"/>
    <!-- <xsl:variable name="collections" select="$annotations/resource[@uri='$uri']/dct:relation/li[a/rinfoex:RelatedContentCollection]"/> -->
    <xsl:variable name="collections" select="$annotations/resource[@uri=$uri]/dct:relation/li[a/rinfoex:RelatedContentCollection]"/>

    <div class="articlecontainer">
      <div class="articlecontent">
	<!-- strip the containing <div>, we should copy the id field though -->
	<xsl:apply-templates/>
      </div>
      <div class="articleannotations">
	<ul>
	  <xsl:for-each select="$collections">
	    <li><xsl:value-of select="dct:title"/>
	    <ul>
	      <xsl:for-each select="dct:hasPart/li">
		<li>
		  <xsl:value-of select="dct:references"/>:
		  <xsl:value-of select="dct:title"/>
		</li>
	      </xsl:for-each>
	    </ul>
	    </li>
	  </xsl:for-each>
	</ul>
      </div>
    </div>
  </xsl:template>

  <xsl:template match="xhtml:div">
    <!-- strip structural <div>s, maybe we should only do that for <div class="section"?> -->
    <xsl:apply-templates/>
  </xsl:template>
    
  <!-- defaultregel: Identity transform -->
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

  <!-- toc handling (do nothing) -->
  <xsl:template match="@*|node()" mode="toc"/>
  
</xsl:stylesheet>

