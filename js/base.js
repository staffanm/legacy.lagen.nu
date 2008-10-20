$(document).ready(function(){
    $("#toc").treeview({
	persist: "location",
        collapsed: true
	});
    /*
    $("#q").autocomplete(docs, {
        matchContains: true,
        selectFirst: false,
        formatItem: function(item) {
            return item.t;
        }
        }).result(function(event, item) {
            location.href = item.l;
    });
    */
	var c = readCookie('style');
	if (c) switchStylestyle(c);
	$(".sidoruta").draggable({cursor:"move",zIndex:"10"});
 
});


function switchStylestyle(styleName)
{
	$('link[@rel*=style][@title]').each(function(i) 
	{
		this.disabled = true;
		if (this.getAttribute('title') == styleName) this.disabled = false;
	});
	createCookie('style', styleName, 365);
}
function switchBoxlayout(layout)
{
    if (layout == "none") {
	$(".kommentar").removeClass("horizboxleft").addClass("hiddenbox");
	$(".referenser").removeClass("horizboxright").addClass("hiddenbox");
    } else if (layout == "horizontal") {
	$(".referenser").removeClass("hiddenbox").addClass("horizboxright");
	$(".kommentar").removeClass("hiddenbox").addClass("horizboxleft");
    } else if (layout == "vertical") {
	$(".kommentar").removeClass("horizboxleft").removeClass("hiddenbox");
	$(".referenser").removeClass("horizboxright").removeClass("hiddenbox");
    }
}

// cookie functions http://www.quirksmode.org/js/cookies.html
function createCookie(name,value,days)
{
	if (days)
	{
		var date = new Date();
		date.setTime(date.getTime()+(days*24*60*60*1000));
		var expires = "; expires="+date.toGMTString();
	}
	else var expires = "";
	document.cookie = name+"="+value+expires+"; path=/";
}
function readCookie(name)
{
	var nameEQ = name + "=";
	var ca = document.cookie.split(';');
	for(var i=0;i < ca.length;i++)
	{
		var c = ca[i];
		while (c.charAt(0)==' ') c = c.substring(1,c.length);
		if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
	}
	return null;
}
function eraseCookie(name)
{
	createCookie(name,"",-1);
}
// /cookie functions