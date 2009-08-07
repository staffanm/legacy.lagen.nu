<?php
define("FERENDA_DIR",'/www/staffan/ferenda.lagen.nu');
define("PYTHON", "/www/staffan/ferenda.lagen.nu/bin/python");

$wgHooks['ArticleSaveComplete'][] = 'fnGenerateOnSave';
function fnGenerateOnSave(&$article, &$user, &$text, &$summary, &$minoredit, 
                        &$watchthis, &$sectionanchor, &$flags, &$revision){

  if ($minoredit == true) {
    // No generate for minor edits
    return true;
  }

  $article = escapeshellarg($article->getTitle());
  $cmd = sprintf("PYTHON_EGG_CACHE=/tmp LC_CTYPE=sv_SE.iso88591 %s %s/Manager.py WikiUpdate %s &> /tmp/GenerateOnSave.txt", PYTHON, FERENDA_DIR, $article);
   $line = system($cmd, $return_var);
   if ($return_var != 0) {
      $fh = fopen("/tmp/GenerateOnSave.txt", 'r');
      $err = fread($fh,filesize("/tmp/GenerateOnSave.txt"));
      mail("staffan@tomtebo.org", "GenerateOnSave error for ".$article, $cmd."\n\n\n".$err);
      throw new Exception($cmd."\n\n".$err);
   }
   return true;
}
?>