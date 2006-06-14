function addEvent(elm, evType, fn, useCapture)
// cross-browser event handling for IE5+, NS6+ and Mozilla/Gecko
// By Scott Andrew
{
  if (elm.addEventListener) {
    elm.addEventListener(evType, fn, useCapture); 
    return true; 
  } else if (elm.attachEvent) {
    var r = elm.attachEvent('on' + evType, fn); 
    return r; 
  } else {
    elm['on' + evType] = fn;
  }
}
/* finds an appropriate box for which to align the comment box */
function FindPreviousBox(element) {
  console.log("FindPreviousBox called: node %s class %s", element.nodeName, element.className)
  if ((element.nodeName == "P" && element.className == "") ||
      (element.nodeName == "P" && element.className == "legaldoc") ||
      (element.nodeName == "H1") ||
      (element.nodeName == "H2")) {
    return element;
  } else if (element.previousSibling == null) {
    return null;
  } else {
    return FindPreviousBox(element.previousSibling);
  }
}

function MoveComments()
{
  var ps = document.getElementsByTagName('p');
  for (var i=0; ps.length >= i; i++) {
    if (ps[i].className.search(/\bcomment\b/) != -1) {
      console.log("Calling FindPreviousBox")
      pe = FindPreviousBox(ps[i].previousSibling)
	ps[i].style.top = pe.offsetTop + "px"
	var spans = ps[i].getElementsByTagName('span');
      for (var j=0; spans.length > j; j++) {
	if (spans[j].className.search(/\blabel\b/) != -1) {
	  spans[j].style.display = "none";
	}
      }
      ps[i].style.display = "block";
             
    }
  }
}
addEvent(window,'load',MoveComments,false);
      
