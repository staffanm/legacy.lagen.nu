<?php
$wgHooks['ArticleSaveComplete'][] = 'fnGenerateOnSave';
function fnGenerateOnSave(&$article, &$user, &$text, &$summary, &$minoredit, 
                        &$watchthis, &$sectionanchor, &$flags, &$revision){

   $parts = explode("/", $article->getTitle());
   if (count($parts) < 2) {
       return true;
   }
   $type = $parts[0];
   $basefile = $parts[1];

   switch($type) {
   case "sfs":
       $module = "SFS.py";
       $basefile = str_replace(":","/",$basefile);
       break;
   case "dom":
       $module = "DV.py";
       // fixme: find out correct basefile ("nja/2004s43" => "HDO/B123-04")
       break;
   default:
       return true;
   }
   $cmd = sprintf("PYTHON_EGG_CACHE=/tmp /usr/local/staffan/bin/python /www/staffan/ferenda.lagen.nu/%s Generate %s &> /tmp/GenerateOnSave.txt", $module, escapeshellarg($basefile));
   $line = system($cmd, &$return_var);
   if ($return_var != 0) {
      $fh = fopen("/tmp/GenerateOnSave.txt", 'r');
      $err = fread($fh,filesize("/tmp/GenerateOnSave.txt"));
      throw new Exception("<pre>".$cmd."\n".$err);
   }
   return true;
}
?>