<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:dct="http://purl.org/dc/terms/"
		xmlns:sparql='http://www.w3.org/2005/sparql-results#'
		xmlns:str="http://exslt.org/strings">

  <xsl:output method="xml" encoding="utf-8"/>

  <xsl:variable name="dokumenturi" select="'http://rinfo.lagrummet.se/publ/sfs/1998:204'"/>

  <xsl:template match="*[@typeof='rinfo:Paragraf']">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
      <xsl:variable name="paragrafuri" select="concat($dokumenturi,'#', @id)"/>
      <xsl:variable name="query">
PREFIX dct:&lt;http://purl.org/dc/terms/&gt;

SELECT DISTINCT ?source WHERE 
{
  {
    ?source dct:references &lt;<xsl:value-of select="$paragrafuri"/>&gt;
  } 
  UNION
  { 
    ?source dct:references ?target . 
    ?target dct:isPartOf &lt;<xsl:value-of select="$paragrafuri"/>&gt;
  } 
  UNION
  { 
    ?source dct:references ?target .
    ?target dct:isPartOf ?container . 
    ?container dct:isPartOf &lt;<xsl:value-of select="$paragrafuri"/>&gt;
  }
}
      </xsl:variable>
      <xsl:variable name="references-url">http://localhost/openrdf-sesame/repositories/lagen.nu?query=<xsl:value-of select="$query"/></xsl:variable>
      <!--
      <xsl:message>Query: <xsl:value-of select="$query"/></xsl:message>
      <xsl:message>Fetching <xsl:value-of select="str:encode-uri($references-url, false())"/></xsl:message>
      -->
      <xsl:variable name="results" select="document(str:encode-uri($references-url,false()))/sparql:sparql/sparql:results/sparql:result"/>
      <div class="backlinks">
	<xsl:for-each select="$results">
	  <p class="backlink"><xsl:value-of select="sparql:binding/sparql:uri"/></p>
	</xsl:for-each>
      </div>
    </xsl:copy>
  </xsl:template>
  
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  
</xsl:stylesheet>