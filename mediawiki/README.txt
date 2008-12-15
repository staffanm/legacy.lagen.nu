A simple extension to Mediawiki which regenerates a page when a
comment about it has been written on an associated wiki.

1. Place the file in $MEDIAWIKI/extensions/

2. Enable it in LocalSettings.php:

require_once("extensions/GenerateOnSave.php");
