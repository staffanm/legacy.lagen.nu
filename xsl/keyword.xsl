<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:rinfoex="http://lagen.nu/terms#"
		xmlns:dct="http://purl.org/dc/terms/"
		exclude-result-prefixes="xht2 dct rdf">

  <xsl:import href="uri.xsl"/>
  <xsl:include href="base.xsl"/>

  <xsl:variable name="dokumenturi" select="/xht2:html/@xml:base"/>

  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//xht2:title"/> - om begreppet | Lagen.nu
  </xsl:template>
  <xsl:template name="metarobots"/>
  <xsl:template name="linkalternate"/>
  <xsl:template name="headmetadata"/>

  <xsl:template match="xht2:h">
      <xsl:if test="@property = 'dct:title'">
	<h1><xsl:value-of select="."/></h1>
	<xsl:variable name="wikidesc" select="$annotations/rdf:Description/dct:description/xht2:div/*"/>
	<xsl:variable name="legaldefs" select="$annotations/rdf:Description/rinfoex:isDefinedBy/*"/>
	<xsl:if test="$wikidesc">
	  <div class="mittruta kommentar">
	    <img src="/img/comment.png" class="inline-icon" width="16" height="16" alt="" title=""/>
	    <xsl:apply-templates select="$wikidesc"/>
	  </div>
	</xsl:if>
	<xsl:if test="not($wikidesc)">
	  Det finns ingen beskrivning av "<xsl:value-of select="."/>" än. Du kanske vill <a href="http://wiki.lagen.nu/index.php?title={.}&amp;action=edit">skriva en?</a>
	</xsl:if>
	<xsl:if test="$legaldefs">
	  <div class="mittruta">
	    <h2>Legaldefinitioner</h2>
	    <xsl:for-each select="$legaldefs">
	      <xsl:sort select="@rdf:about"/>
	      <xsl:variable name="localurl"><xsl:call-template name="localurl"><xsl:with-param name="uri" select="@rdf:about"/></xsl:call-template></xsl:variable>
	      <a href="{$localurl}"><xsl:value-of select="rdfs:label"/></a><br/>
	    </xsl:for-each>
	  </div>
	</xsl:if>
      </xsl:if>
  </xsl:template>

  <xsl:template match="xht2:a|a">
    <xsl:call-template name="link">
    </xsl:call-template>
  </xsl:template>

  <!-- defaultregel: kopierar alla element från xht2 till
       default-namespacet -->
  <xsl:template match="xht2:*|*">
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

  <!-- refs mode -->
  <xsl:template match="xht2:h" mode="refs">
    <xsl:variable name="rattsfall" select="$annotations/rdf:Description/dct:subject/rdf:Description"/>

    <xsl:if test="$rattsfall">
      <div class="sidoruta">
	<h2>Rättsfall</h2>
	<xsl:call-template name="rattsfall">
	  <xsl:with-param name="rattsfall" select="$rattsfall"/>
	</xsl:call-template>
      </div>
    </xsl:if>
  </xsl:template>

  <xsl:template match="*" mode="refs"/>
  

  <xsl:template name="rattsfall">
    <xsl:param name="rattsfall"/>
      <xsl:for-each select="$rattsfall">
	<xsl:sort select="@rdf:about"/>
	<xsl:variable name="tuned-width">
	  <xsl:call-template name="tune-width">
	    <xsl:with-param name="txt" select="dct:description"/>
	    <xsl:with-param name="width" select="200"/>
	    <xsl:with-param name="def" select="200"/>
	  </xsl:call-template>
	</xsl:variable>
	<xsl:variable name="localurl"><xsl:call-template name="localurl"><xsl:with-param name="uri" select="@rdf:about"/></xsl:call-template></xsl:variable>
	<a href="{$localurl}"><b><xsl:value-of select="dct:identifier"/></b></a>:
	<xsl:choose>
	  <xsl:when test="string-length(dct:description) > 200">
	    <xsl:value-of select="normalize-space(substring(dct:description, 1, $tuned-width - 1))" />...
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:value-of select="dct:description"/>
	  </xsl:otherwise>
	</xsl:choose>
	<br/>
      </xsl:for-each>
  </xsl:template>


  <!-- kommentar mode -->
  <xsl:template match="*|@*" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>
  
</xsl:stylesheet>

