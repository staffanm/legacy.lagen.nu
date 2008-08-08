<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
		xmlns="http://www.w3.org/1999/xhtml"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xht2="http://www.w3.org/2002/06/xhtml2/"
		xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
		xmlns:dct="http://dublincore.org/documents/dcmi-terms/"
		xmlns:rinfo="http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#">

  <xsl:import href="uri.xsl"/>
  <xsl:import href="tune-width.xsl"/>
  <xsl:include href="base.xsl"/>
  
  <xsl:variable name="alla_rattsfall"
		select="document('../data/sfs/parsed/dv-rdf.xml')"/>
  <xsl:variable name="dokumenturi" select="/xht2:html/@xml:base"/>
  
  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//xht2:title"/> (<xsl:value-of select="//xht2:meta[@property='dct:alternate']/@content"/>) | Lagen.nu
  </xsl:template>

  <!-- FIXME: anpassa till xht2-datat -->
  <xsl:template name="metarobots">
    <xsl:if test="preamble/revoked">
      <xsl:if test="number(translate($today,'-','')) > number(translate(/preamble/revoked,'-',''))">
	<meta name="robots" content="noindex,follow"/>
      </xsl:if>
    </xsl:if>
  </xsl:template>

  <!-- FIXME: anpassa till xht2-datat -->
  <xsl:template name="linkalternate">
    <link rel="alternate" type="text/plain" title="Plain text">
      <xsl:attribute name="href">/<xsl:value-of select="/law/preamble/sfsid"/>.txt</xsl:attribute>
    </link>
    <link rel="alternate" type="application/xml" title="XML">
      <xsl:attribute name="href">/<xsl:value-of select="/law/preamble/sfsid"/>.xml</xsl:attribute>
    </link>
  </xsl:template>

  <xsl:template name="headmetadata">
      <xsl:comment>all övrig metadata</xsl:comment>
  </xsl:template>

  <xsl:template match="xht2:h">
    <xsl:choose>
      <xsl:when test="@property = 'dct:title'">
	<h1><xsl:value-of select="."/></h1>
      </xsl:when>
      <xsl:when test="@class = 'underrubrik'">
	<h3><xsl:value-of select="."/></h3>
      </xsl:when>
      <xsl:otherwise>
	<h2><xsl:value-of select="."/></h2>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="xht2:a">
    <xsl:call-template name="link"/>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div class="{@class}" id="{@id}"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="xht2:dl[@role='contentinfo']">
    <!-- emit nothing -->
  </xsl:template>

  <xsl:template match="xht2:section[@role='secondary']/xht2:section">
    <h2>Ändring: <xsl:value-of select="xht2:dl/xht2:dd[@property='dct:title']"/></h2>
    <xsl:apply-templates/>
  </xsl:template>

  
  <xsl:template match="*">
    <xsl:element name="{name()}">
      <xsl:apply-templates select="@*|node()"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@*">
    <xsl:copy><xsl:apply-templates/></xsl:copy>
  </xsl:template>

  <!-- REFS MODE -->
  <xsl:template match="xht2:dl[@role='contentinfo']" mode="refs">
    <!-- Den stora metadata-definitionslistan innehåller en massa som
         inte är intressant att visa för slutanvändaren. Filtrera ut
         de intressanta bitarna -->
    <dl>
      <dt>Departement</dt>
      <dd><xsl:value-of select="xht2:dd[@rel='dct:creator']"/></dd>
      <dt>Utfärdad</dt>
      <dd><xsl:value-of select="xht2:dd[@property='rinfo:utfardandedatum']"/></dd>
      <dt>Ändring införd t.o.m.</dt>
      <dd><xsl:value-of select="xht2:dd[@rel='rinfo:konsolideringsunderlag']"/></dd>
      <dt>Källa</dt>
      <dd><a href="http://62.95.69.15/cgi-bin/thw?%24%7BHTML%7D=sfst_lst&amp;%24%7BOOHTML%7D=sfst_dok&amp;%24%7BSNHTML%7D=sfst_err&amp;%24%7BBASE%7D=SFST&amp;%24%7BTRIPSHOW%7D=format%3DTHW&amp;BET={xht2:dd[@property='rinfo:fsNummer']}">Regeringskansliets rättsdatabaser</a></dd>
      <dt>Senast hämtad</dt>
      <dd><xsl:value-of select="//xht2:meta[@property='rinfoex:senastHamtad']/@content"/></dd>
    </dl>
    <!-- 
    <p>Rättsfall:<br/>
    <xsl:call-template name="rattsfall">
      <xsl:with-param name="rattsfall" select="$alla_rattsfall/rdf:RDF/rdf:Description[@rdf:about=$dokumenturi]/dct:isReferencedBy/rdf:Description"/>
    </xsl:call-template>
    </p>
    -->
  </xsl:template>

  <xsl:template match="xht2:section[@typeof='rinfo:Paragraf']" mode="refs">
    
    <xsl:variable name="paragrafuri" select="concat($dokumenturi,'#', @id)"/>
    <xsl:variable name="rattsfall" select="document('../data/sfs/parsed/dv-rdf.xml')/rdf:RDF/rdf:Description[@rdf:about=$paragrafuri]/dct:isReferencedBy/rdf:Description"/>
    <xsl:variable name="inford" select="//xht2:a[@rel='rinfo:inforsI' and @href=$paragrafuri]"/>
    <xsl:variable name="andrad" select="//xht2:a[@rel='rinfo:ersatter' and @href=$paragrafuri]"/>
    <xsl:variable name="upphavd" select="//xht2:a[@rel='rinfo:upphaver' and @href=$paragrafuri]"/>

    <xsl:if test="$rattsfall or $inford or $andrad or $upphavd">
      <p id="refs-{@id}">
	<b><xsl:value-of select="@id"/></b><br/>
	<xsl:call-template name="andringsnoteringar">
	  <xsl:with-param name="typ" select="'Införd'"/>
	  <xsl:with-param name="andringar" select="$inford"/>
	</xsl:call-template>
	
	<xsl:call-template name="andringsnoteringar">
	  <xsl:with-param name="typ" select="'Ändrad'"/>
	  <xsl:with-param name="andringar" select="$andrad"/>
	</xsl:call-template>
	
	<xsl:call-template name="andringsnoteringar">
	  <xsl:with-param name="typ" select="'Upphävd'"/>
	  <xsl:with-param name="andringar" select="$upphavd"/>
	</xsl:call-template>
	
	<xsl:call-template name="rattsfall">
	  <xsl:with-param name="rattsfall" select="$rattsfall"/>
	</xsl:call-template>
      </p>
    </xsl:if>
  </xsl:template>

  <xsl:template name="andringsnoteringar">
    <xsl:param name="typ"/>
    <xsl:param name="andringar"/>
    <xsl:if test="$andringar">
      <xsl:value-of select="$typ"/>: SFS
      <xsl:for-each select="$andringar">
	<!-- här kan man tänka sig göra uppslag i en xml-fil som mappar
	     förarbetsid:n till förarbetsrubriker -->
	<a href="#{../../../@id}"><xsl:value-of select="../..//xht2:dd[@property='rinfo:fsNummer']"/></a><xsl:if test="position()!= last()">, </xsl:if>
      </xsl:for-each>
      <br/>
    </xsl:if>
  </xsl:template>

  <xsl:template name="rattsfall">
    <xsl:param name="rattsfall"/>
      <xsl:for-each select="$rattsfall">
	<xsl:variable name="tuned-width">
	  <xsl:call-template name="tune-width">
	    <xsl:with-param name="txt" select="dct:description"/>
	    <xsl:with-param name="width" select="70"/>
	    <xsl:with-param name="def" select="70"/>
	  </xsl:call-template>
	</xsl:variable>
	<xsl:variable name="localurl">
	  <xsl:call-template name="localurl">
	    <xsl:with-param name="uri" select="@rdf:about"/>
	  </xsl:call-template>
	</xsl:variable>
	<a href="{$localurl}"><b><xsl:value-of select="dct:identifier"/></b></a>:
	<xsl:value-of select="normalize-space(substring(dct:description, 1, $tuned-width - 1))" />...
	<br/>
      </xsl:for-each>
  </xsl:template>
  
  <xsl:template match="xht2:h" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <xsl:template match="xht2:section[@class='upphavd']" mode="refs">
    <!-- emit nothing -->
  </xsl:template>
    
  <xsl:template match="xht2:section[@role='secondary']" mode="refs">
    <!-- emit nothing -->
  </xsl:template>

  <xsl:template match="*|@*" mode="refs">
    <xsl:apply-templates mode="refs"/>
  </xsl:template>


  <!-- KOMMENTARER MODE -->
  <xsl:template match="xht2:section[@role='main']" mode="kommentarer">
    <ul>
      <xsl:apply-templates mode="kommentarer"/>
    </ul>
  </xsl:template>

  <xsl:template match="xht2:section[@typeof='rinfo:Kapitel']" mode="kommentarer">
    <li>kr: <xsl:value-of select="xht2:h[@class='kapitelrubrik']"/>
    <ul>
      <xsl:apply-templates mode="kommentarer"/>
    </ul>
    </li>
  </xsl:template>

  <xsl:template match="xht2:h[@property='dct:title']" mode="kommentarer">
    <!--<li>Not emitting title</li>-->
  </xsl:template>

  <xsl:template match="xht2:h[@class='kapitelrubrik']" mode="kommentarer">
    <!--<li>Not emitting kapitelrubrik</li>-->
  </xsl:template>
  
  <xsl:template match="xht2:h" mode="kommentarer">
    <li><b>h: </b><xsl:value-of select="."/>
    <!-- select ../xht2:h,
         loop until this headline is found (identify by id),
         then output a li for each xht2:h[@class='underrubrik']
	 until a regular headline is found
    -->
    </li>
  </xsl:template>

  <xsl:template match="xht2:h[@class='underrubrik']" mode="kommentarer">
    <li><i>uh: </i><xsl:value-of select="."/></li>
  </xsl:template>

  <!-- filter the rest -->
  <xsl:template match="xht2:dl[@role='contentinfo']" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>
  <xsl:template match="xht2:section[@role='secondary']" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>
  <xsl:template match="xht2:p" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>
  <xsl:template match="xht2:span" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>
  <xsl:template match="xht2:section[@class='upphavd']" mode="kommentarer">
    <!-- emit nothing -->
  </xsl:template>
  
</xsl:stylesheet>