<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- this is a standalone template for formatting links. It's used by
       test.xslt and xsl/verdict.xsl -->
<xsl:template match="link" name="link">
  <xsl:choose>
    <xsl:when test="@href">
      <a href="{@href}">
	<xsl:value-of select="."/>
      </a>
    </xsl:when>
    <xsl:when test="@type='docref'">
      <xsl:call-template name="docref"/>
    </xsl:when>
    <xsl:when test="@verdict">
      <a href="/dom/{@verdict}">
	<xsl:value-of select="."/>
      </a>
    </xsl:when>
    <xsl:otherwise>
      <xsl:variable name="explicitchapter">
	<xsl:value-of select="@chapter"/>
      </xsl:variable>
      <xsl:variable name="chapter">
	<xsl:if test="$hasChapters or (@law and @chapter)">
	  <xsl:choose>
	    <xsl:when test="@chapter"><xsl:value-of select="@chapter"/></xsl:when>
	    <xsl:otherwise><xsl:value-of select="ancestor::chapter/@id"/></xsl:otherwise>
	  </xsl:choose>
	</xsl:if>
      </xsl:variable>
      <xsl:variable name="explicitsection">
	<xsl:value-of select="@section"/>
      </xsl:variable>
      <xsl:variable name="section">
	<xsl:choose>
	  <xsl:when test="@section"><xsl:value-of select="@section"/></xsl:when>
	  <xsl:otherwise><xsl:value-of select="../../@id"/></xsl:otherwise>
	</xsl:choose>
      </xsl:variable>
      <xsl:variable name="piece">
	<xsl:choose>
	  <xsl:when test="@piece"><xsl:value-of select="@piece"/></xsl:when>
	  <xsl:otherwise>1</xsl:otherwise>
	</xsl:choose>
      </xsl:variable>
      <xsl:variable name="usechapter">
	<xsl:choose>
	  <xsl:when test="@law and @chapter">
	    1
	  </xsl:when>
	  <xsl:when test="$hasChapters and $sectionOneCount > 1">
	    1
	  </xsl:when>
	  <xsl:otherwise>
	    0
	  </xsl:otherwise>
	</xsl:choose>
      </xsl:variable>
      <xsl:variable name="usesection">
	<xsl:choose>
	  <xsl:when test="@section or @piece or @item">
	    1
	  </xsl:when>
	  <xsl:otherwise>
	    0
	  </xsl:otherwise>
	</xsl:choose>
      </xsl:variable>
      <!--
      <xsl:comment>
	usechapter     : <xsl:value-of select="number($usechapter)"/>
	explicitchapter: <xsl:value-of select="$explicitchapter"/>
	chapter        : <xsl:value-of select="$chapter"/>
	usesection     : <xsl:value-of select="number($usesection)"/>
	explicitsection: <xsl:value-of select="$explicitsection"/>
	section        : <xsl:value-of select="$section"/>
	piece          : <xsl:value-of select="$piece"/>
	item           : <xsl:value-of select="@item"/>
      </xsl:comment>
      -->
      <a>
	<xsl:attribute name="href">
	  <xsl:if test="@law">/<xsl:value-of select="@law"/></xsl:if>
	  <xsl:if test="@chapter or @section or @piece or @lawref">#<xsl:if test="@lawref">L<xsl:value-of select="@lawref"/></xsl:if>
	  <xsl:choose>
	    <xsl:when test="@lawref"/>
	    <xsl:when test="number($usechapter) = 1">K<xsl:value-of select="string($chapter)"/></xsl:when>
	  </xsl:choose>
	  <xsl:choose>
	    <xsl:when test="@lawref"></xsl:when>
	    <xsl:when test="number($usesection) = 1">P<xsl:value-of select="$section"/></xsl:when>
	  </xsl:choose>
	  <xsl:choose>
	    <xsl:when test="@piece">S<xsl:value-of select="@piece"/></xsl:when>
	    <xsl:when test="@item">S<xsl:value-of select="@piece"/></xsl:when><!-- only ever used if we're in a list and refer to another list element -->
	  </xsl:choose>
	  <xsl:if test="@item">N<xsl:value-of select="@item"/></xsl:if>
	  </xsl:if>
	</xsl:attribute>
	<xsl:value-of select="."/>
      </a>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>
</xsl:stylesheet>
