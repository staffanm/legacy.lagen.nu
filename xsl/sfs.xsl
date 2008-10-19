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
  <xsl:import href="tune-width.xsl"/>
  <xsl:include href="base.xsl"/>
  
  <xsl:param name="cases"/>
  <xsl:param name="kommentarer"/>

  <xsl:variable name="dokumenturi" select="/xht2:html/@xml:base"/>

  <xsl:variable name="docmetadata">
    <dl id="refs-dokument">
      <dt>Departement</dt>
      <dd rel="dct:creator" resource="{//xht2:dd[@rel='dct:creator']/@href}"><xsl:value-of select="//xht2:dd[@rel='dct:creator']"/></dd>
      <dt>Utfärdad</dt>
      <dd property="rinfo:utfardandedatum" datatype="xsd:date"><xsl:value-of select="//xht2:dd[@property='rinfo:utfardandedatum']"/></dd>
      <dt>Ändring införd</dt>
      <dd rel="rinfo:konsolideringsunderlag" href="{//xht2:dd[@rel='rinfo:konsolideringsunderlag']/@href}"><xsl:value-of select="//xht2:dd[@rel='rinfo:konsolideringsunderlag']"/></dd>
      <xsl:if test="//xht2:dd[@property='rinfoex:tidsbegransad']">
	<dt>Tidsbegränsad</dt>
	<dd property="rinfoex:tidsbegransad"><xsl:value-of select="//xht2:dd[@property='rinfoex:tidsbegransad']"/></dd>
      </xsl:if>
      <dt>Källa</dt>
      <dd rel="dct:publisher" resource="http://lagen.nu/org/2008/regeringskansliet"><a href="http://62.95.69.15/cgi-bin/thw?%24%7BHTML%7D=sfst_lst&amp;%24%7BOOHTML%7D=sfst_dok&amp;%24%7BSNHTML%7D=sfst_err&amp;%24%7BBASE%7D=SFST&amp;%24%7BTRIPSHOW%7D=format%3DTHW&amp;BET={//xht2:dd[@property='rinfo:fsNummer']}">Regeringskansliets rättsdatabaser</a></dd>
      <dt>Senast hämtad</dt>
      <dd property="rinfoex:senastHamtad" datatype="xsd:date"><xsl:value-of select="//xht2:meta[@property='rinfoex:senastHamtad']/@content"/></dd>
    </dl>
  </xsl:variable>
  
  <xsl:variable name="toc">
    <xsl:apply-templates mode="kommentarer"/>
  </xsl:variable>

  
  <!-- Implementationer av templates som anropas från base.xsl -->
  <xsl:template name="headtitle">
    <xsl:value-of select="//xht2:title"/>
    <xsl:if test="//xht2:meta[@property='dct:alternate']/@content">
      (<xsl:value-of select="//xht2:meta[@property='dct:alternate']/@content"/>)
    </xsl:if> | Lagen.nu
  </xsl:template>

  <xsl:template name="metarobots"/>

  <xsl:template name="linkalternate">
    <link rel="alternate" type="text/plain" title="Plain text">
      <xsl:attribute name="href">/<xsl:value-of select="//xht2:meta[@property='rinfo:fsNummer']/@content"/>.txt</xsl:attribute>
    </link>
    <link rel="alternate" type="application/xml" title="XHTML2">
      <xsl:attribute name="href">/<xsl:value-of select="//xht2:meta[@property='rinfo:fsNummer']/@content"/>.xht2</xsl:attribute>
    </link>
  </xsl:template>

  <xsl:template name="headmetadata"/>

  <xsl:template match="xht2:h">
    <xsl:choose>
      <xsl:when test="@property = 'dct:title'">
	<h1 property="dct:title"><xsl:value-of select="."/></h1>
	<div class="sidoruta">
	  <xsl:copy-of select="$docmetadata"/>
	  <xsl:if test="normalize-space($toc)">
	    <ul id="toc">
	      <li>Innehållsförteckning
	      <xsl:copy-of select="$toc"/>
	      </li>
	    </ul>
	  </xsl:if>
	</div>
	<div class="sidoruta kommentar">
	  <h2>Kommentarer</h2>
	  <p><a class="editlink" href="http://wiki.lagen.nu/index.php?title=sfs/{//xht2:dd[@property='rinfo:fsNummer']}&amp;action=edit">[redigera]</a></p>
	  <xsl:copy-of select="document($kommentarer)/rdf:RDF/rdf:Description[@rdf:about=$dokumenturi]/dct:description/*"/>
	</div>
      </xsl:when>
      <xsl:when test="@class = 'underrubrik'">
	<h3><xsl:for-each select="@*">
	    <xsl:attribute name="{name()}"><xsl:value-of select="." /></xsl:attribute>
	  </xsl:for-each><xsl:value-of select="."/></h3>
      </xsl:when>
      <xsl:otherwise>
	<h2><xsl:for-each select="@*">
	    <xsl:attribute name="{name()}"><xsl:value-of select="." /></xsl:attribute>
	  </xsl:for-each><xsl:value-of select="."/></h2>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="xht2:a">
    <xsl:call-template name="link"/>
  </xsl:template>

  <xsl:template match="xht2:section">
    <div>
      <xsl:if test="@id">
	<xsl:attribute name="id"><xsl:value-of select="@id"/></xsl:attribute>
	<xsl:attribute name="about"><xsl:value-of select="//xht2:html/@about"/>#<xsl:value-of select="@id"/></xsl:attribute>
      </xsl:if>
      <xsl:if test="@class">
	<xsl:attribute name="class"><xsl:value-of select="@class"/></xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <xsl:template match="xht2:dl[@role='contentinfo']">
    <!-- emit nothing -->
  </xsl:template>

  <xsl:template match="xht2:section[@typeof='rinfo:Paragraf']">
    <div class="paragraf" id="{@id}" about="{//xht2:html/@about}#{@id}">
      <xsl:apply-templates/>
      <!-- plocka fram referenser kring/till denna paragraf -->
      <xsl:variable name="paragrafuri" select="concat($dokumenturi,'#', @id)"/>
      
      <xsl:variable name="rattsfall" select="document($cases)/rdf:RDF/rdf:Description[@rdf:about=$paragrafuri]/dct:isReferencedBy/rdf:Description"/>
      <xsl:variable name="inford" select="//xht2:a[@rel='rinfo:inforsI' and @href=$paragrafuri]"/>
      <xsl:variable name="andrad" select="//xht2:a[@rel='rinfo:ersatter' and @href=$paragrafuri]"/>
      <xsl:variable name="kommentar" select="document($kommentarer)/rdf:RDF/rdf:Description[@rdf:about=$paragrafuri]/dct:description/*"/>
      <xsl:variable name="upphavd" select="//xht2:a[@rel='rinfo:upphaver' and @href=$paragrafuri]"/>
      <xsl:if test="$rattsfall or $inford or $andrad or $upphavd">
	<p id="refs-{@id}" class="sidoruta referenser">
	  <!--
	      <span class="refboxlabel"><xsl:value-of select="xht2:p/xht2:span[@class='paragrafbeteckning']"/>: </span>
	  -->
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
      <xsl:if test="$kommentar">
	<p id="ann-{@id}" class="sidoruta kommentar">
	<xsl:copy-of select="document($kommentarer)/rdf:RDF/rdf:Description[@rdf:about=$paragrafuri]/dct:description"/>
	</p>
      </xsl:if>
    </div>
  </xsl:template>
  
  <xsl:template name="andringsnoteringar">
    <xsl:param name="typ"/>
    <xsl:param name="andringar"/>
    <xsl:if test="$andringar">
      <xsl:value-of select="$typ"/>: SFS
      <xsl:for-each select="$andringar">
	<!-- här kan man tänka sig göra uppslag i en xml-fil som mappar
	     förarbetsid:n till förarbetsrubriker -->
	<a href="#{concat(substring-before(../../../@id,':'),'-',substring-after(../../../@id,':'))}"><xsl:value-of select="../..//xht2:dd[@property='rinfo:fsNummer']"/></a><xsl:if test="position()!= last()">, </xsl:if>
      </xsl:for-each>
      <br/>
    </xsl:if>
  </xsl:template>

  <xsl:template name="rattsfall">
    <xsl:param name="rattsfall"/>
      <xsl:for-each select="$rattsfall">
	<xsl:sort select="@rdf:about"/>
	<xsl:variable name="tuned-width">
	  <xsl:call-template name="tune-width">
	    <xsl:with-param name="txt" select="dct:description"/>
	    <xsl:with-param name="width" select="80"/>
	    <xsl:with-param name="def" select="80"/>
	  </xsl:call-template>
	</xsl:variable>
	<xsl:variable name="localurl"><xsl:call-template name="localurl"><xsl:with-param name="uri" select="@rdf:about"/></xsl:call-template></xsl:variable>
	<a href="{$localurl}"><b><xsl:value-of select="dct:identifier"/></b></a>:
	<xsl:choose>
	  <xsl:when test="string-length(dct:description) > 80">
	    <xsl:value-of select="normalize-space(substring(dct:description, 1, $tuned-width - 1))" />...
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:value-of select="dct:description"/>
	  </xsl:otherwise>
	</xsl:choose>
	<br/>
      </xsl:for-each>
  </xsl:template>

  <xsl:template match="xht2:section[@role='main']">
    <div class="konsolideradtext"><xsl:apply-templates/></div>
  </xsl:template>
		
  <xsl:template match="xht2:section[@role='secondary']">
    <div class="andringar"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="xht2:section[@role='secondary']/xht2:section">
    <xsl:variable name="year" select="substring-before(xht2:dl/xht2:dd[@property='rinfo:fsNummer'],':')"/>
    <xsl:variable name="nr" select="substring-after(xht2:dl/xht2:dd[@property='rinfo:fsNummer'],':')"/>
    <div class="andring" id="{concat(substring-before(@id,':'),'-',substring-after(@id,':'))}" about="{@about}">
      <!-- titel eller sfsnummer, om ingen titel finns -->
      <h2><xsl:choose>
	<xsl:when test="xht2:dl/xht2:dd[@property='dct:title']">
	  <xsl:value-of select="xht2:dl/xht2:dd[@property='dct:title']"/>
	</xsl:when>
	<xsl:otherwise>
	  <xsl:value-of select="xht2:dl/xht2:dd[@property='rinfo:fsNummer']"/>
	</xsl:otherwise>
      </xsl:choose></h2>
      <xsl:if test="(number($year) > 1998) or (number($year) = 1998 and number($nr) >= 306)">

	<p><a href="http://62.95.69.3/SFSdoc/{substring($year,3,2)}/{substring($year,3,2)}{format-number($nr,'0000')}.PDF">Officiell version (PDF)</a></p>
      </xsl:if>
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <xsl:template match="xht2:p[@typeof='rinfo:Stycke']">
    <p id="{@id}" about="{//xht2:html/@about}#{@id}">
      <span class="platsmarkor">
	<xsl:choose>
	  <xsl:when test="substring-after(@id,'S') = '1'">
	    <xsl:if test="substring-after(@id,'K')">
	      <xsl:value-of select="substring-before(substring-after(@id,'K'),'P')"/> kap.
	    </xsl:if>
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:value-of select="substring-after(@id,'S')"/> st.
	  </xsl:otherwise>
	</xsl:choose></span>
      <xsl:apply-templates/>
    </p>
  </xsl:template>

  <!-- FIXME: in order to be valid xhtml1, we must remove unordered
       lists from within paragraphs, and place them after the
       paragraph. This turns out to be tricky in XSLT, the following
       is a non-working attempt -->
  <!--
  <xsl:template match="xht2:p">
    <p>
      <xsl:if test="@id">
	<xsl:attribute name="id"><xsl:value-of select="@id"/></xsl:attribute>
      </xsl:if>
      <xsl:for-each select="text()|*">
	<xsl:if test="not(name()='ul')">
	  <xsl:element name="XX{name()}">
	    <xsl:apply-templates select="text()|*"/>
	  </xsl:element>
	</xsl:if>
	<xsl:if test="not(name(node()[1]))">
	  TXT:<xsl:value-of select="."/>END
	</xsl:if>
      </xsl:for-each>
    </p>
    <xsl:if test="ul">
      <xsl:apply-templates select="ul"/>
    </xsl:if>
  </xsl:template>
  -->
  
  <!-- defaultregler: översätt allt från xht2 till xht1-namespace, men inga ändringar i övrigt
  -->
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
    <!-- moved to top
    <dl id="refs-dokument" class="sidoruta">
      <dt>Departement</dt>
      <dd rel="dct:creator" resource="{xht2:dd[@rel='dct:creator']/@href}"><xsl:value-of select="xht2:dd[@rel='dct:creator']"/></dd>
      <dt>Utfärdad</dt>
      <dd property="rinfo:utfardandedatum" datatype="xsd:date"><xsl:value-of select="xht2:dd[@property='rinfo:utfardandedatum']"/></dd>
      <dt>Ändring införd</dt>
      <dd rel="rinfo:konsolideringsunderlag" href="{xht2:dd[@rel='rinfo:konsolideringsunderlag']/@href}"><xsl:value-of select="xht2:dd[@rel='rinfo:konsolideringsunderlag']"/></dd>
      <xsl:if test="xht2:dd[@property='rinfoex:tidsbegransad']">
	<dt>Tidsbegränsad</dt>
	<dd property="rinfoex:tidsbegransad"><xsl:value-of select="xht2:dd[@property='rinfoex:tidsbegransad']"/></dd>
      </xsl:if>
      <dt>Källa</dt>
      <dd rel="dct:publisher" resource="http://lagen.nu/org/2008/regeringskansliet"><a href="http://62.95.69.15/cgi-bin/thw?%24%7BHTML%7D=sfst_lst&amp;%24%7BOOHTML%7D=sfst_dok&amp;%24%7BSNHTML%7D=sfst_err&amp;%24%7BBASE%7D=SFST&amp;%24%7BTRIPSHOW%7D=format%3DTHW&amp;BET={xht2:dd[@property='rinfo:fsNummer']}">Regeringskansliets rättsdatabaser</a></dd>
      <dt>Senast hämtad</dt>
      <dd property="rinfoex:senastHamtad" datatype="xsd:date"><xsl:value-of select="//xht2:meta[@property='rinfoex:senastHamtad']/@content"/></dd>
    </dl>

    -->
  </xsl:template>

  <xsl:template match="*" mode="refs">
    <!-- default: emit nothing -->
  </xsl:template>

  <!--
      helst skulle vi ha alla sidorutor i högerspalten, men så att
      varje box är i höjd med sin paragraf, men det verkar omöjligt
      att få till en lösning (vare sig med css eller js) som funkar
      för alla fall. Saker som gör det svårt:

      * lagar med 1000+ sidorutor (inkomstskattelagen) - tar en
      evighet att visa

      * paragrafer med väldigt många rättsfall (så att refboxen blir
      högre än sin paragraf, exv marknadsföringslagen 4 §) - boxarna
      får inte täcka över varandra, och lagtexten måste ändå vara
      sammanhållen det måste vara tydligt.

      * det måste se OK ut även vid utskrift.

      Tills vidare får vi köra som lagen.nu 1.0, dvs med sidorutor
      under paragraferna
      
  <xsl:template match="xht2:section[@typeof='rinfo:Paragraf']" mode="refs">
    <xsl:variable name="paragrafuri" select="concat($dokumenturi,'#', @id)"/>
    <xsl:variable name="rattsfall" select="document('../data/sfs/parsed/dv-rdf.xml')/rdf:RDF/rdf:Description[@rdf:about=$paragrafuri]/dct:isReferencedBy/rdf:Description"/>
    <xsl:variable name="inford" select="//xht2:a[@rel='rinfo:inforsI' and @href=$paragrafuri]"/>
    <xsl:variable name="andrad" select="//xht2:a[@rel='rinfo:ersatter' and @href=$paragrafuri]"/>
    <xsl:variable name="upphavd" select="//xht2:a[@rel='rinfo:upphaver' and @href=$paragrafuri]"/>

    <xsl:if test="$rattsfall or $inford or $andrad or $upphavd">
      <p id="refs-{@id}" class="refbox">
	<span class="refboxlabel"><xsl:value-of select="xht2:p/xht2:span[@class='paragrafbeteckning']"/>: </span>
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
  -->

  <!-- KOMMENTARER MODE -->
  <xsl:template match="xht2:section[@role='main']" mode="kommentarer">
    <!-- moved to top 
    <xsl:variable name="toc"><xsl:apply-templates mode="kommentarer"/></xsl:variable>
    <xsl:if test="normalize-space($toc)">
      <ul id="toc">
	<li>Innehållsförteckning
	<ul>
	  <xsl:apply-templates mode="kommentarer"/>
	</ul>
	</li>
      </ul>
    </xsl:if>
    -->
  </xsl:template>

  <xsl:template match="xht2:section[@typeof='rinfo:Avdelning']" mode="kommentarer">
    <li class="toc-avdelning"><a href="#{@id}"><xsl:value-of select="xht2:h[@class='avdelningsrubrik']"/>: <xsl:value-of select="xht2:h[@class='avdelningsunderrubrik']"/></a>
    <ul><xsl:apply-templates mode="kommentarer"/></ul>
    </li>
  </xsl:template>

  <xsl:template match="xht2:section[@typeof='rinfo:Kapitel']" mode="kommentarer">
    <li class="toc-kapitel"><a href="#{@id}"><xsl:value-of select="xht2:h[@class='kapitelrubrik']"/></a>
    <xsl:if test="xht2:h[@id]">
      <ul><xsl:apply-templates mode="kommentarer"/></ul>
    </xsl:if>
    </li>
  </xsl:template>

  <xsl:template match="xht2:h[@property='dct:title']" mode="kommentarer">
    <!--<li>Not emitting title</li>-->
  </xsl:template>

  <xsl:template match="xht2:h[@class='kapitelrubrik']" mode="kommentarer">
    <!--<li>Not emitting kapitelrubrik</li>-->
  </xsl:template>
  <xsl:template match="xht2:h[@class='avdelningsrubrik']" mode="kommentarer">
    <!--<li>Not emitting kapitelrubrik</li>-->
  </xsl:template>
  <xsl:template match="xht2:h[@class='avdelningsunderrubrik']" mode="kommentarer">
    <!--<li>Not emitting kapitelrubrik</li>-->
  </xsl:template>
  
  <xsl:template match="xht2:h" mode="kommentarer">
    <li class="toc-rubrik"><a href="#{@id}"><xsl:value-of select="."/></a>
    <!-- for proper handling of underrubriker
	 select ../xht2:h,
         loop until this headline is found (identify by id),
         then output a li for each xht2:h[@class='underrubrik']
	 until a regular headline is found
    -->
    </li>
  </xsl:template>

  <xsl:template match="xht2:h[@class='underrubrik']" mode="kommentarer">
    <li class="toc-underrubrik"><a href="#{@id}"><xsl:value-of select="."/></a></li>
  </xsl:template>

  <xsl:template match="xht2:section[@typeof='rinfo:Bilaga']" mode="kommentarer">
    <li class="toc-bilaga"><a href="#{@id}"><xsl:value-of select="xht2:h"/></a></li>
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