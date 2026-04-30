	function IncludeJS(srcUrl){
		document.write('<script type="text/javascript" src="' + srcUrl + '" charset="utf-8"></' + 'script>');
	}
	
	function IncludeCSS(srcUrl){
		document.write('<link rel="stylesheet" href="' + srcUrl + '" type="text/css" media="screen" />');
	}
	
	function getNameFromPath(strFilepath) {
		var objRE = new RegExp(/([^\/\\]+)$/);
		var strName = objRE.exec(strFilepath);
		if (strName == null) {
			return null;
		}
		else {
			return strName[0];
		}
	}
	
	//이름가져오기
	function getNameFromPath(strFilepath) {
		var objRE = new RegExp(/([^\/\\]+)$/);
		var strName = objRE.exec(strFilepath);
		if (strName == null) {
			return null;
		}
		else {
			return strName[0];
		}
	}
	
	//첨부파일용량체크
	function filesizeCheck(obj,size) {
		//첨부파일용량체크
		var totalSize = 0;
		var maxSize = 1024 * 1024 * size; //단위는 M
		filesize = 0;
		$('input[name^="' + obj + '"]', 'form[name=myform]').each(function(){
			if($(this).val() != ""){
				var file = this.files;
				filesize = filesize + file[0].size; 
			}
		});
		
		if(filesize > maxSize){
			return 'no';
		}else{
			return 'ok';
		}
	}

	
	//첨부파일 다운로드
	function filedownload(filename,realFilename){
		location.href="/config/download.html?filename=" + filename + "&realFilename=" + realFilename;
	}
	
	//첨부파일 추가
	function addUploadFile(inputFile,inputFilenameValue,inputRealFilenameValue,UploadContainerId,maxCount,lang) {
		var obj, len, id, lastValue, lastCheck, file_area, file_id, file_route, field;
		obj = $('input[name="' + inputFile + '[]"]', 'form[name=myform]');
		len = obj.length;
		
		if(len > 0){
			lastValue = obj.eq(len - 1).val();
			lastCheck = $('input[name="' + inputFilenameValue + '[]"]', 'form[name=myform]').eq(len - 1).val();
			
			if (lastValue == '' && lastCheck == ''){
				obj.eq(len - 1).parent('div').remove();
				addUploadFile(inputFile,inputFilenameValue,inputRealFilenameValue,UploadContainerId,maxCount,lang);
				return;
			}	
		}
		
		if (len < maxCount	) {
			id = Math.floor((Math.random() * 10000) % (99999 - 10000)) + 10000;
			file_area = inputFile + '_file_area' + id;
			file_id = inputFile + '_file_id' + id
			file_route = inputFile + '_file_route' + id;
	
			field = $('<div class="file-box" class="post_file" id="' + file_area + '" style="display:none;">'+
						'<div class="file-name"><span id="' + file_route + '"></span></div>'+
						'<button type="button" class="btn small btn-file-delete" onClick="removeUploadFile(\'' + file_area + '\')"></button>'+
						'<input type="file" name="' + inputFile +'[]" id="' + file_id + '" onchange="showFilename(\'' + file_route + '\',this.value,\'' + file_area + '\',this);" style="display:none;"/>'+
						'<input type="hidden" name="' + inputFilenameValue + '[]" value="" />'+
						'<input type="hidden" name="' + inputRealFilenameValue + '[]" value="" />'+
					'</div>');
					
			field.appendTo('#' + UploadContainerId);
			$('#'+file_id).click();
		} else {
			if(maxCount == '1'){
				if(lang == 'eng'){
					alert('Delete existing files and add them.');
				}else{
					alert('기존파일 삭제후 추가하세요.');	
				}
			}else{
				if(lang == 'eng'){
					alert('Uploads are limited to '+ maxCount +'.');
				}else{
					alert('최대 ' + maxCount + '개까지만 업로드 가능합니다.');
				}
			}
		}
	}
	
	function showFilename(file_route,filename,file_area){
		var num = filename.lastIndexOf("\\"); 
		var filename = filename.substr(num+1); 
		$('#' + file_route).text(filename);
		$('#' + file_area).css('display','flex');
		
	}
	
	function removeUploadFile(file_area){
		Field = document.getElementById(file_area);
		$(Field).remove();
	}
	
	//전체검색 queryString
	function queryStringHeaderSearch(){
		var queryString = "";
		var sKeyword = $.trim($("input[name=sKeyword]","form[name=headerSearchform]").val());
		
		if(sKeyword != "") queryString = queryString + "&sKeyword=" + sKeyword;	
		
		return queryString
	}
	
	//검색 queryString
	function queryStringSearch(){
		var queryString = "";
		var boardCode = $.trim($("input[name=boardCode]","form[name=searchForm]").val());
		var sKeyword = $.trim($("input[name=sKeyword]","form[name=searchForm]").val());
		var sArea = $.trim($("select[name=sArea]","form[name=searchForm]").val());
		var sCatecode = $.trim($("input[name=sCatecode]","form[name=searchForm]").val());
		var mine = $.trim($("input[name=mine]","form[name=searchForm]").val());
		var sFlagRoom = $.trim($("input[name=sFlagRoom]","form[name=searchForm]").val());
		var sFlagService = $.trim($("input[name=sFlagService]","form[name=searchForm]").val());
		var sFlagTech = $.trim($("input[name=sFlagTech]","form[name=searchForm]").val());
		var sCate = $.trim($("select[name=sCate]","form[name=searchForm]").val());
		
		if(boardCode != "") queryString = queryString + "&boardCode=" + boardCode;
		if(sKeyword != "") queryString = queryString + "&sKeyword=" + sKeyword;	
		if(sArea != "") queryString = queryString + "&sArea=" + sArea;	
		if(sCatecode != "") queryString = queryString + "&sCatecode=" + sCatecode;
		if(mine != "") queryString = queryString + "&mine=" + mine;
		if(sFlagRoom != "") queryString = queryString + "&sFlagRoom=" + sFlagRoom;
		if(sFlagService != "") queryString = queryString + "&sFlagService=" + sFlagService;
		if(sFlagTech != "") queryString = queryString + "&sFlagTech=" + sFlagTech;
		if(sCate != "") queryString = queryString + "&sCate=" + sCate;
		
		return queryString
	}
	
	//기본 queryString
	function queryString(){
		
		var queryString = "";
		var page = $.trim($("input[name=page]","form[name=myform]").val());
		var sKeyword = $.trim($("input[name=sKeyword]","form[name=myform]").val());
		var boardCode = $.trim($("input[name=boardCode]","form[name=myform]").val());
		var sArea = $.trim($("select[name=boardCode]","form[name=myform]").val());
		var sCatecode = $.trim($("input[name=sCatecode]","form[name=myform]").val());
		var mine = $.trim($("input[name=mine]","form[name=myform]").val());
		var sFlagRoom = $.trim($("input[name=sFlagRoom]","form[name=myform]").val());
		var sFlagService = $.trim($("input[name=sFlagService]","form[name=myform]").val());
		var sFlagTech = $.trim($("input[name=sFlagTech]","form[name=myform]").val());
		var sCate = $.trim($("select[name=sCate]","form[name=myform]").val());
		
		if(page != "") queryString = queryString + "&page=" + page;
		if(boardCode != "") queryString = queryString + "&boardCode=" + boardCode;
		if(sKeyword != "") queryString = queryString + "&sKeyword=" + sKeyword;	
		if(sArea != "") queryString = queryString + "&sArea=" + sArea;	
		if(sCatecode != "") queryString = queryString + "&sCatecode=" + sCatecode;
		if(mine != "") queryString = queryString + "&mine=" + mine;
		if(sFlagRoom != "") queryString = queryString + "&sFlagRoom=" + sFlagRoom;
		if(sFlagService != "") queryString = queryString + "&sFlagService=" + sFlagService;
		if(sFlagTech != "") queryString = queryString + "&sFlagTech=" + sFlagTech;
		if(sCate != "") queryString = queryString + "&sCate=" + sCate;
		
		return queryString
	}
	
	//mobile touch link
	/*$(function(){
		$('a').on('touchstart', function() {
			var touchValue = 'noTouch';
			$(this).on('touchmove',function(){touchValue = 'touch'});
			$(this).on('touchend',function(){
				if(touchValue == 'noTouch'){
					var link = $(this).attr('href');
					location.href = link;
				}	
			});
		});	
	});*/
	
	//gotoUrl
	function sendBoard(boardCode){
		location.href = '?boardCode=' + boardCode;
	}	
	
	function formatNumber(num) {
		var str = String(num)
		var re = /(-?[0-9]+)([0-9]{3})/;
		
		while (re.test(str)) {
			str = str.replace(re, "$1,$2");
		}
		return str;
	}
	
		
	function setNum(num){
		if(num < 10){
			num = "0" + num;
		}
		
		return num;
	}
	
	//리스트 이미지
	/*$(function(){
		setImg();
		$(window).resize(function(){setImg()});	
		
		function setImg(){
			var obj = $('.setImg');
			obj.each(function(){
				var boxHeight = $(this).parent('.setImgBox').height();
				var imgHeight = $(this).height();
				
				console.log(boxHeight + ' / ' + imgHeight);
				
				if(boxHeight > imgHeight && imgHeight > 0 ){
					//console.log(imgHeight);
					$(this).css('margin-top',(boxHeight - imgHeight)/2 + 'px')
					$(this).css('margin-bottom',(boxHeight - imgHeight)/2 + 'px')
				}else{
					$(this).css('margin-top','0')
					$(this).css('margin-bottom','0')
				}
			});	
		}
	});*/
	
	//글자수
	function textcount(obj,maxcount){
		var strValue = $('#' + obj).val(); 
		var strLen = strValue.length + 1;
		
		if(strLen > maxcount){
			alert("제한 글자를 " + maxcount + "자를 초과하였습니다.");
			$('#' + obj).val(strValue.substring(0, maxcount - 2));
		}
	}
	
	
	function goScroll(id){
		window.scrollTo({
			top: $(id).offset().top - 100, // 문서의 전체 높이로 스크롤
			//behavior: 'smooth' // 부드러운 스크롤 효과
		});
	}
