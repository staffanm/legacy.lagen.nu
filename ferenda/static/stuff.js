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

function removeEvent(elm, evType, fn )
{
  if (elm.removeEventListener) {
    elm.removeEventListener( type, fn, false );
    return true;
  } else if (elm.detachEvent) {
    var r = elm.detachEvent( "on"+type, fn);
    return r;
  } else {
    elm["on" + type+fn] = null;
  }
}

function Logmsg(msg) {
  if (window.console) {
    window.console.log(msg);
  }
}


/* finds an appropriate box for which to align the comment box */
function FindPreviousBox(element) {
  Logmsg("FindPreviousBox called: node %s class %s", element.nodeName, element.className)
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
      Logmsg("Calling FindPreviousBox")
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

function PrepareEditFields()
{
  
  Logmsg("installing handlers");
  iCnt = 0;
  var ps = document.getElementsByTagName('p');
  for (var i=0; ps.length > i; i++) {
    if (ps[i].className.search(/\bclicktoedit\b/) != -1) {
      iCnt++;
      addEvent(ps[i],'mouseover',ShowBox,false);
      addEvent(ps[i],'mouseout',HideBox);
      addEvent(ps[i], 'click', EditBox);
    }
  }
  Logmsg("installed " + iCnt + "handlers");
}

function ShowBox(e)
{
  //e.target.style.visibility = 'visible';
  Logmsg("showing box");
  this.className.replace('visible','');
}

function HideBox(e)
{
  //e.target.style.visibility = 'hidden';
  Logmsg("'hiding' box");
  this.className += ' invisible';
}

function EditBox(e)
{
  Logmsg("making box editable");
  var forms = this.getElementsByTagName("form");
  if (forms.length > 0) {
    Logmsg("it was already editable");
    return;
  }

  while (this.firstChild) {
    this.removeChild(this.firstChild);
  }
  form = document.createElement("form");
  form.method = "POST";
  form.action = "/save/" + document.body.id + "/" + this.id
  textarea = document.createElement("textarea");
  text = document.createTextNode("Skriv text");
  textarea.appendChild(text);
  textarea.name = "text";
  submit = document.createElement("input");
  submit.type = "submit";
  submit.value = "Spara";
  form.appendChild(textarea);
  form.appendChild(submit);
  this.appendChild(form);
}


/* addEvent(window,'load',MoveComments,false); */
addEvent(window,'load',PrepareEditFields,false);      
