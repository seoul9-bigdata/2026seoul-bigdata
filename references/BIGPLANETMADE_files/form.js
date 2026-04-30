/* 폼 */

$(document).ready(function(){
    /* 첨부파일 */
    /* 250617 start */
    var $formWrap = $('.form-wrap');
    var $formFileWrap = $formWrap.find('.file-wrap');

    if($formFileWrap.length > 0){
        var btnFileUpload = '.file-wrap .button-wrap input[type="file"]';
        var btnFileUploadLabel = '.file-wrap .button-wrap label';
        $(document).on('change', btnFileUpload, function(){
            var $thisFileWrap = $(this).parents('.file-wrap');
            var $thisFileList = $thisFileWrap.find('.file-list-wrap');
            var $file =$(this).clone();
            var limit = (typeof $thisFileWrap.data('limit') == 'undefined') ? 5 : $thisFileWrap.data('limit');

            if($(this).val() != ""){
                setFileUploadForm($thisFileWrap, $file, limit);
            }
        });

        $(document).on('click', btnFileUploadLabel, function(){
            var $thisInput = $(this).find('input');
            var $thisFileWrap = $(this).parents('.file-wrap');
            var limit = (typeof $thisFileWrap.data('limit') == 'undefined') ? 5 : $thisFileWrap.data('limit');
            
            //if($thisInput.attr('disabled') == 'disabled'){
                //alert('첨부파일은 '+ limit +'개까지 등록 가능합니다.\nUploads are limited to '+ limit +'.');
           // }
        });

        var btnFileDelete = '.file-wrap .file-list-wrap .file-box .btn-file-delete';
        $(document).on('click', btnFileDelete, function(){
            var $thisFileWrap = $(this).parents('.file-wrap');
            var $thisFileList = $(this).parents('.file-list-wrap');            
            var $thisFileBox = $(this).parents('.file-box');
            $thisFileBox.remove();
            var uploadFile = $thisFileList.find('.file-box').length;
            console.log(uploadFile);
            if(uploadFile < 5){
                $thisFileWrap.find('input[type="file"]').removeAttr('disabled');
            }

        });
    }
    /* 250617 end */


    /* 링크 */
    var $linkWrap = $formWrap.find('.link-wrap');
    if($linkWrap.length > 0){
        var $btnLinkUpload = $linkWrap.find('.link-input-wrap .btn-link-add');
        $btnLinkUpload.on('click', function(){
            var $thisLinkWrap = $(this).parents('.link-wrap');
            var lan = (typeof $thisLinkWrap.data('lan') == 'undefined') ? 'kor' : $thisLinkWrap.data('lan');
            var $thisLinkInputBox = $thisLinkWrap.find('.link-input-wrap .text-input-box input[type=text]');
            if($thisLinkInputBox.val() == ""){
                if(lan == 'kor'){
                    alert('url을 입력하세요.');
                }else{
                    alert('Please enter your URL.');
                }
                $thisLinkInputBox.focus();
            }else{
                setLinkUploadForm($thisLinkWrap);
            }
        });

        var btnLinkDelete = '.link-wrap .link-list-wrap .link-box .btn-link-delete';
        $(document).on('click', btnLinkDelete, function(){
            var $thisLinkBox = $(this).parents('.link-box');
            $thisLinkBox.remove();
        });
    }


    /* sns */
    var $snsWrap = $formWrap.find('.form-sns-wrap');
    if($snsWrap.length > 0){
        var $btnSnsUpload = $snsWrap.find('.sns-input-wrap .btn-sns-add');
        $btnSnsUpload.on('click', function(){
            var $thisSnsWrap = $(this).parents('.form-sns-wrap');
            var lan = (typeof $thisSnsWrap.data('lan') == 'undefined') ? 'kor' : $thisSnsWrap.data('lan');
            var $thisSnsSelectBox = $thisSnsWrap.find('.sns-input-wrap .select-box select');
            var $thisSnsInputBox = $thisSnsWrap.find('.sns-input-wrap .text-input-box input[type=text]');
            if($thisSnsSelectBox.val() == ""){
                if(lan == 'kor'){
                    alert('sns를 선택하세요.');
                }else{
                    alert('Please select SNS.');
                }
            }else if($thisSnsInputBox.val() == ""){
                if(lan == 'kor'){
                    alert('sns ID 또는 URL을 입력하세요.');
                }else{
                    alert('Please enter your SNS ID or URL.');
                }
                $thisSnsInputBox.focus();
            }else{
                setSnsUploadForm($thisSnsWrap);
            }
        });

        var btnSnsDelete = '.form-sns-wrap .sns-list-wrap .sns-input-box .btn-sns-delete';
        $(document).on('click', btnSnsDelete, function(){
            var $thisSnsBox = $(this).parents('.sns-input-box');
            $thisSnsBox.remove();
        });
    }


    /* language */
    var $languageWrap = $formWrap.find('.language-wrap');
    if($languageWrap.length > 0){
        var $btnLanguageUpload = $languageWrap.find('.lan-input-wrap .btn-lan-add');
        $btnLanguageUpload.on('click', function(){
            var $thisLanguageWrap = $(this).parents('.language-wrap');
            var lan = (typeof $thisLanguageWrap.data('lan') == 'undefined') ? 'kor' : $thisLanguageWrap.data('lan');
            var $thisLanguageBox = $thisLanguageWrap.find('.lan-input-wrap .select-box select.language');
            var $thisLevelBox = $thisLanguageWrap.find('.lan-input-wrap .select-box select.level');
            if($thisLanguageBox.val() == ""){
                if(lan == 'kor'){
                    alert('언어를 선택하세요.');
                }else{
                    alert('Please select a language.');
                }
            }else if($thisLevelBox.val() == ""){
                if(lan == 'kor'){
                    alert('언어 사용 가능 수준을 선택하세요.');
                }else{
                    alert('Select your language availability level.');
                }
            }else{
                setLanguageUploadForm($languageWrap);
            }
        });

        var btnLanguageDelete = '.language-wrap .lan-list-wrap .language-box .btn-lan-delete';
        $(document).on('click', btnLanguageDelete, function(){
            var $thisLanguageBox = $(this).parents('.language-box');
            $thisLanguageBox.remove();
        });
    }

});

function setFileUploadForm(wrap, el, limit){
    var html = '';
    var $fileWrap = $(wrap);
    var $fileList = $fileWrap.find('.file-list-wrap');

    html += '<div class="file-box">';
    html += '   <div class="file-name"><span>'+$(el).val()+'</span></div>';
    html += '   <button type="button" class="btn small btn-file-delete"></button>';
    html += '</div>';

    $fileList.append(html);
    $fileList.find('.file-box').last().append(el);
    setFileFormUpdate($fileWrap, limit);
}


/* 250617 */
function setFileFormUpdate(wrap, limit){
    var $fileWrap = $(wrap);
    var $buttonWrap = $fileWrap.find('.button-wrap');
    var $label = $buttonWrap.find('label');
    var $input = $buttonWrap.find('input[type=file]');
    var count = (typeof $fileWrap.data('count') == 'undefined') ? 0 : $fileWrap.data('count');
    var id = $fileWrap.data('id');
    var $fileList = $fileWrap.find('.file-list-wrap');
    var uploadFile = $fileList.find('.file-box').length;

    var newCount = count + 1;
    var newId = id + '-' + newCount;

    $label.attr('for', newId);
    $input.attr('id', newId);
    if(uploadFile == limit){
        $input.attr('disabled', 'disabled');
    }
    $fileWrap.data('count', newCount);
}


function setLinkUploadForm(wrap){
    var $linkWrap = $(wrap);
    var $linkInputBox = $linkWrap.find('.link-input-wrap .text-input-box input[type=text]');
    var val = $linkInputBox.val();
    var $linkList = $linkWrap.find('.link-list-wrap');
    var count = (typeof $linkWrap.data('count') == 'undefined') ? 0 : $linkWrap.data('count');
    var id = $linkWrap.data('id') + '-' + count;
    var newCount = count + 1;

    var html = '';
    html += '<div class="link-box">';
    html += '   <div class="text-input-box">';
    html += '       <input type="text" name="reference[]" value="'+ val +'" id="'+id+'">';
    html += '   </div>';
    html += '   <button type="button" class="btn small btn-minus btn-link-delete"><span>삭제</span></button>';
    html += '</div>';

    $linkList.append(html);
    $linkWrap.data('count', newCount);
    console.log( $linkWrap.data('count'));
    $linkInputBox.val("");
}


function setSnsUploadForm(wrap){
    var $snsWrap = $(wrap);
    var $snsSelectBox = $snsWrap.find('.sns-input-wrap .select-box select');
    var $snsInputBox = $snsWrap.find('.sns-input-wrap .text-input-box input[type=text]');
    var snsType = $snsSelectBox.val();
    var val = $snsInputBox.val();
    var $snsList = $snsWrap.find('.sns-list-wrap');
    var count = (typeof $snsWrap.data('count') == 'undefined') ? 0 : $snsWrap.data('count');
    var id = $snsWrap.data('id') + '-' + count;
    var newCount = count + 1;

    var html = '';
    html += '<div class="sns-input-box">';
    html += '    <div class="select-box">';
    html += '       <div class="select">';
    html += '            <select name="sns[]" id="sns-type-'+count+'">';
    html += '               <option value="">SNS</option>';
    html += '               <option value="youtube">YouTube</option>';
    html += '               <option value="instagram">Instagram</option>';
    html += '               <option value="facebook">Facebook</option>';
    html += '               <option value="tiktok">TikTok</option>';
    html += '               <option value="x">X</option>';
    html += '               <option value="ect">기타</option>';
    html += '            </select>';
    html += '       </div>';
    html += '   </div>';
    html += '   <div class="input-box">';
    html += '       <div class="text-input-box"><input type="text" name="snsurl[]" value="' + val + '" placeholder="ID / URL" id="sns-val-'+count+'"></div>';
    html += '       <button type="button" class="btn small btn-minus btn-sns-delete"><span>삭제</span></button>';
    html += '   </div>';
    html += '</div>';


    $snsList.append(html);
    $snsWrap.data('count', newCount);
    $snsList.find('.sns-input-box').last().find('.select-box select').val(snsType).prop('selected', true);
    $snsSelectBox.val('').prop('selected', true);
    $snsInputBox.val("");
}


/* 250617 */
function setLanguageUploadForm(wrap){
    var $languageWrap = $(wrap);
    var $clone = $languageWrap.find('.lan-input-wrap .lan-select-wrap').clone();
    var $lanBox = $languageWrap.find('.lan-input-wrap .select-box select.language');
    var $levelBox = $languageWrap.find('.lan-input-wrap .select-box select.level');
    var language = $lanBox.val();
    var level = $levelBox.val();
    var $languageList = $languageWrap.find('.lan-list-wrap');
    var count = (typeof $languageWrap.data('count') == 'undefined') ? 0 : $languageWrap.data('count');
    var lanId = $languageWrap.data('id') + '-language-' + count;
    var levelId = $languageWrap.data('id') + '-level-' + count;
    var newCount = count + 1;

    var html = '';
    html += '<div class="language-box">';
    html += '   <button type="button" class="btn-lan-delete"><span>삭제</span></button>';
    html += '</div>';


    /*
    var languageTxt = $languageWrap.find('.lan-input-wrap .select-box select.language option:selected').text();
    var levelTxt = $languageWrap.find('.lan-input-wrap .select-box select.level option:selected').text();
    var $languageList = $languageWrap.find('.lan-list-wrap');
    var count = (typeof $languageWrap.data('count') == 'undefined') ? 0 : $languageWrap.data('count');
    var lanId = $languageWrap.data('id') + '-language-' + count;
    var levelId = $languageWrap.data('id') + '-level-' + count;
    var newCount = count + 1;

    var html = '';
    html += '<div class="language-box">';
    html += '   <div class="language-val-wrap">';
    html += '       <div class="val">'+languageTxt+'</div>';
    html += '       <div class="val">'+levelTxt+'</div>';
    html += '   </div>';
    html += '   <button type="button" class="btn-lan-delete"><span>삭제</span></button>';
    html += '   <input type="hidden" name="" id="'+lanId+'" value="'+language+'">';
    html += '   <input type="hidden" name="" id="'+levelId+'" value="'+level+'">';
    html += '</div>';



    $languageList.append(html);
    $languageWrap.data('count', newCount);*/

    $languageList.append(html);    
    $languageWrap.data('count', newCount);

    var $currentSelectBox = $languageList.find('.language-box').last();
    $currentSelectBox.prepend($clone);
    
    var $currentLanSelect = $currentSelectBox.find('.select-box select.language');
    var $currentLevelSelect = $currentSelectBox.find('.select-box select.level');
    
    $currentLanSelect.val(language).prop('selected', true);
    $currentLevelSelect.val(level).prop('selected', true);

    $currentLanSelect.attr('id', lanId);
    $currentLanSelect.attr('name', 'language[]');

    $currentLevelSelect.attr('id', levelId);
    $currentLevelSelect.attr('name', 'languagelevel[]');

    $lanBox.val('').prop('selected', true);
    $levelBox.val('').prop('selected', true);
}