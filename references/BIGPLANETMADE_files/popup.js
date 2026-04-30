// JScript 파일
IncludeCSS("/popup/css/style.css")	//팝업 스타일시트 인클루드
var Popup
Popup = function (idx, ptop, pleft, pwidth, pheight, pScrollbars, autosize, Body) {
	this.idx = idx;
	this.ptop = ptop;
	this.pleft = pleft;
	this.pwidth = pwidth;
	this.pheight = pheight;
	this.pScrollbars = pScrollbars;
	this.autosize = autosize;
	this.Body = Body;

	this.oPopup = $("<div id='Popup'" + idx + "></div>");
}

Popup.prototype.showPop = function () {
	this.oPopup.attr("id", "LayerPopup");
	this.oPopup.css({
		zIndex: "8" + this.idx,
		position: "absolute",
		top: this.ptop + "px",
		left: this.pleft + "px",
		width: this.pwidth + "px",
		height: this.pheight + "px",
		//overflow: ((this.pScrollbars == "1") ? "auto" : "visible")
		overflow: "hidden"
	}).html(this.Body).appendTo($("body"));
}
	
Popup.prototype.hidePop = function () {
	this.oPopup.hide();
}

function initPopup(){
	Url = "/popup/popupcheck.php";
	Parameters = "";

	$.ajax({
		url: Url,
		data: Parameters,
		dataType: "text",
		success: function (Rst) {
			if(Rst != ''){
				var tpop = eval(Rst)
				
				for(j = 0; j < tpop.length; j++){
					var pInfo = tpop[j];
					
					idx = pInfo[0];
					ptype = pInfo[1];
					ptop = pInfo[2];
					pleft = pInfo[3];
					pwidth = pInfo[4];
					pheight = pInfo[5];
					pClose = pInfo[6];
					autosize = pInfo[7];
					
					pToolbar = "no"
					pLocation = "no"
					pStatus = "no"
					pMenubar = "no"
					pScrollbars = "no"
					pResizable = "no"
					
					var pName = "Popup"+idx
					var eventCookie = getCookie(pName); 
					
					if(ptype == "W"){
						if (eventCookie != "no"){
							Wopen(idx, ptop, pleft, pwidth, pheight, autosize);
						}
					}else if(ptype == "L"){
						if (eventCookie != "no"){
							Lopen(idx, ptop, pleft, pwidth, pheight, autosize);
						}
					}
				}
			}
		},

		error: function (xhr, textStatus, errorThrown) {
			var exceptShow = "상태 코드: " + xhr.status;
			exceptShow += ",  비정상으로 종료되었습니다.(error_0001)";
			alert(exceptShow);
			alert(xhr.responseText);
		}
	});
}

function getCookie(name) { 
    var Found = false 
    var start, end 
    var i = 0 

    while(i <= document.cookie.length) { 
      start = i 
      end = start + name.length 
      if(document.cookie.substring(start, end) == name) { 
          Found = true 
          break 
      }
      
      i++ 
    } 

    if(Found == true) { 
      start = end + 1 
      end = document.cookie.indexOf(";", start) 
      
      if(end < start) 
          end = document.cookie.length 
      
      return document.cookie.substring(start, end) 
    } 
    return "" 
}

function setCookie( name, value, expiredays ){ 
		var todayDate = new Date(); 
		todayDate.setDate( todayDate.getDate() + expiredays ); 
		document.cookie = name + "=" + escape( value ) + "; path=/; expires=" + todayDate.toGMTString() + ";" 
}

function Wopen(idx, ptop, pleft, pwidth, pheight, autosize) {
	Url = "/popup/popup.php?idx="+idx;
	Name = "Popup"+idx;
	
	var pheight = parseInt(pheight) + parseInt(30);
	
	if (navigator.userAgent.indexOf('Chrome')>-1 || navigator.userAgent.indexOf('Safari')>-1) { //크롬, 사파리일때
		var pwidth2 = parseInt(pwidth) + parseInt(4);
		var pheight2 = parseInt(pheight) + parseInt(4); 
		
		pToolbar = "no"
		pLocation = "no"
		pStatus = "no"
		pMenubar = "no"
		pScrollbars = "no"
		pResizable = "no"
		
		Features = "top="+ptop+",left="+pleft+",width="+pwidth2+",height="+pheight2+",scrollbars="+pScrollbars+",toolbar="+pToolbar+",status="+pStatus+",resizable="+pResizable+",menubar="+pMenubar+",location="+pLocation;
	}else{ //크롬, 사파리말고 모두
		Features = "top="+ptop+",left="+pleft+",width="+pwidth+",height="+pheight+",scrollbars="+pScrollbars+",toolbar="+pToolbar+",status="+pStatus+",resizable="+pResizable+",menubar="+pMenubar+",location="+pLocation;
	}
	
	//크롬, 사파리 무시
	Features = "top="+ptop+",left="+pleft+",width="+pwidth+",height="+pheight+",scrollbars="+pScrollbars+",toolbar="+pToolbar+",status="+pStatus+",resizable="+pResizable+",menubar="+pMenubar+",location="+pLocation;
	
  	window.open(Url, Name, Features);
}

var popupBox = [];

function Lopen(idx, ptop, pleft, pwidth, pheight, pScrollbars, autosize){
	try{
		Url = "/popup/getPopup.php";
		Parameters = "idx=" + idx;

		$.ajax({
			url: Url,
			data: Parameters,
			dataType: "html",
			success: function (Rst) {
				if (Rst != '') {
					if (autosize == "Y") {

						var divEl = $("<div style='position:absoult; left:-10000px;'></div>")

						divEl.html(Rst);

						//divEl.appendTo($("body"));
						$("body").append(divEl)

						pop = $("#popupWrap", divEl);

						pwidth = pop.width();
						pheight = pop.height();
						
						divEl.remove();
					}

					popupBox[idx] = new Popup(idx, ptop, pleft, pwidth, parseInt(pheight) + parseInt(30), pScrollbars, autosize, Rst);
					popupBox[idx].showPop();

					HideSelectBox();
				}
				
				//팝업 resizing
				setPopup();
				$(window).resize(function(){setPopup()});
				
				function setPopup(){
					$('.popupWrap').each(function(){
						var pleft = $(this).attr('pleft');
						var ptop = $(this).attr('ptop');
						var pwidth = $(this).attr('pwidth');
						var pheight = $(this).attr('pheight');
						var winwidth = $(window).width() - 40;
						var mobileheight = winwidth * pheight / pwidth;
						
						if(winwidth > 800){
							$(this).parents('#LayerPopup').css({'left':pleft + 'px','top': ptop + 'px','width': pwidth + 'px','height': parseInt(pheight) + 30 + 'px'});
							$(this).css({'width': pwidth + 'px','height': parseInt(pheight) + 30 + 'px'});
						}else{
							$(this).parents('#LayerPopup').css({'left':'20px','top':'20px','width': winwidth + 'px','height': parseInt(mobileheight) + 30 + 'px'});
							$(this).css({'width': winwidth + 'px','height': parseInt(mobileheight) + 30 + 'px'});
							
						}					
					});
				}
			},

			error: function (xhr, textStatus, errorThrown) {
				var exceptShow = "상태 코드: " + xhr.status;
				exceptShow += ",  비정상으로 종료되었습니다.(error_0002)";
				alert(exceptShow);
			}
		});
	}catch(e) {}
}

function linkPopup(linkType, linkUrl){
	switch(linkType){
		case 0 : break;
		case 1 : location.href=linkUrl; break;
		case 2 : window.open(linkUrl); break;
		case 3 : location.href=linkUrl; break;
	}
}

function HideSelectBox(){
	var box = document.getElementsByTagName("select")
	
	for(i = 0; i < box.length; i++){
		box[i].style.visibility = "hidden";
	}
}

function ShowSelectBox(){
	box = document.getElementsByTagName("select")
	
	for(i = 0; i < box.length; i++){
		box[i].style.visibility = "visible";
	}
}

function HidePopup(idx){
	popupBox[idx].hidePop();
	
	var Flag = true;
	var pop = document.getElementsByName("LayerPopup")
	for(i = 0; i < pop.length; i++){
		if(pop[i].style.display != "none")
			Flag = false;
	}
	
	if(Flag) ShowSelectBox();
}

function SaveCookiesAndClose(idx, name, term) {
	setCookie(name, "no", 1); // 1일동안 쿠키를 보존합니다.

	HidePopup(idx);
}

function CloseWin(idx){
	HidePopup(idx);
}

$(document).ready(function () {
	initPopup();
});