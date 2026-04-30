var filter = "win16|win32|win64|mac|macintel";
var mobileIs = false;

if (navigator.platform) {
	if (filter.indexOf(navigator.platform.toLowerCase()) < 0) {
		mobileIs = true;
	}
}

let win_w;
let win_h;
let win_sct;
let doc_sct;

var scrollY = 0;
var lastScrollTop = 0;

let footerH;

function setScreenSize() {
	let vh = window.innerHeight * 0.01;
	document.documentElement.style.setProperty('--vh', `${vh}px`);
}
setScreenSize();
window.addEventListener('resize', setScreenSize);


$(document).ready(function () {});

$(window).on("load", function () {
    //alert(window.navigator.userAgent);
    var browser = window.navigator.userAgent.toLowerCase();
    if(browser.indexOf('kakaotalk') > -1){
        location.href = 'kakaotalk://web/openExternal?url='+window.location.href;
    }
    //console.log(window.location.host + window.location.pathname + window.location.search);
    // 카카오 브라우저에서 네이버 모바일 웹을 외부 브라우저로 열기
    //location.href = 'intent://'+window.location.host + window.location.pathname + window.location.search+'#Intent;scheme='+window.location.protocol+';action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;end';

    function getHeaderLeft(){
        let hl = document.querySelector('.header-wrap').getBoundingClientRect().left;
        document.documentElement.style.setProperty('--hl', `${hl}px`);
    }
    getHeaderLeft();
    window.addEventListener('resize', getHeaderLeft);

    function setFooterH(){
        footerH = document.querySelector('footer').offsetHeight;
        document.documentElement.style.setProperty('--footer', `${footerH}px`);
    }
    setFooterH();
    window.addEventListener('resize', setFooterH);

});

// 공통
$(function(){

    gsap.registerPlugin(ScrollTrigger, ScrollSmoother);
    //ScrollTrigger.normalizeScroll(true);

    const lenis = new Lenis();
    lenis.on('scroll', ScrollTrigger.update);

    gsap.ticker.add((time)=>{
        lenis.raf(time * 1000);
    })

    gsap.ticker.lagSmoothing(0);

    let mm = gsap.matchMedia();

    window.addEventListener('resize', function(event) {
        ScrollTrigger.update
    }, true);
    ScrollTrigger.refresh();
    ScrollTrigger.config({ ignoreMobileResize: true });


    const html = document.querySelector('html');
    const body = document.querySelector('body');


    const header = document.querySelector('header');

    /*window.addEventListener('scroll', function(){
        var scrt = document.querySelector('html').scrollTop;
        var vh = document.documentElement.style.getPropertyValue('--vh').replace('px', '') * 100;
        var val = 150;
        
        if((document.querySelector('.main') != null) || (document.querySelector('.contents.company') != null)){
            val = vh;
        }

        if(scrt > val){
            header.classList.add('down');
        }else{
            header.classList.remove('down');
        }
    });*/


    const scroller = document.querySelectorAll('.scroller');
    if(scroller.length > 0){
        let isDown = [];
        let startX = [];
        let scrollLeft = [];

        scroller.forEach((el, idx) => {
            const onScrollStart = (e) => {
                isDown[idx] = true;
                startX[idx] = getPageX(e) - el.offsetLeft;
                scrollLeft[idx] = el.scrollLeft;
            };
        
            const onScrollMove = (e) => {
                if(!isDown[idx]) return;
                e.preventDefault();
                const x = getPageX(e) - el.offsetLeft;
                const walk = (x - startX[idx]) * 3;
                el.scrollLeft = scrollLeft[idx] - walk;
            };
        
            const onScrollEnd = () => {
                isDown[idx] = false;
            };
        
            const getPageX = (e) => {
                var isTouches = e.touches ? true : false;
                return isTouches ? e.touches[0].pageX : e.pageX;
            };

            const onLayoutSet = (e) => {
                var scw = el.scrollWidth;
                var clw = el.clientWidth;
                var child = $(el).children()[0];
                if(!el.classList.contains('center')){
                    if((scw - clw) > 0){
                        child.classList.add('over');
                    }else{
                        child.classList.remove('over');
                    }
                }
            }; onLayoutSet();

            el.addEventListener('mousedown', onScrollStart);
            el.addEventListener('touchstart', onScrollStart);
            el.addEventListener('mousemove', onScrollMove);
            el.addEventListener('touchmove', onScrollMove);
            el.addEventListener('mouseup', onScrollEnd);
            el.addEventListener('mouseleave', onScrollEnd);
            el.addEventListener('touchend', onScrollEnd);
            window.addEventListener('resize', onLayoutSet);

        });
    }

    $('select').niceSelect();
    /*const selectBoxEl = document.querySelectorAll('.select-box');
    if(selectBoxEl.length > 0){
        let isSelectDown = [];
        let selectStartY = ['a', 'b'];
        let selectScrollY = [];
        let scrt;

        selectBoxEl.forEach((selectbox, idx) => {
            var optionWrap = selectbox.querySelector('.option-wrap');
            
            const onSelectScrollStart = (e) => {
                isSelectDown[idx] = true;
                selectStartY[idx] = getSelectPageX(e) - optionWrap.offsetTop;
                selectScrollY[idx] = optionWrap.scrollTop;
                scrt = document.documentElement.scrollTop;
            };

            const onSelectScrollMove = (e) => {
                if(!isSelectDown[idx]) return;
                e.preventDefault();
                const y = getSelectPageX(e) - optionWrap.offsetTop;
                const walk = (y - selectStartY[idx]) * 3;
                optionWrap.scrollTop = selectScrollY[idx] - walk;
                document.documentElement.scrollTop = scrt;
            };

            const onSelectScrollEnd = (e) => {
                isSelectDown[idx] = false;
            }

            const getSelectPageX = (e) => {
                var isTouches = e.touches ? true : false;
                return isTouches ? e.touches[0].pageY : e.pageY;
            }

            const onSelectClick = (e) => {
                e.stopPropagation();
            };

            optionWrap.addEventListener('mousedown', onSelectScrollStart);
            optionWrap.addEventListener('touchstart', onSelectScrollStart);
            optionWrap.addEventListener('mousemove', onSelectScrollMove);
            optionWrap.addEventListener('touchmove', onSelectScrollMove);
            optionWrap.addEventListener('mouseup', onSelectScrollEnd);
            optionWrap.addEventListener('touchend', onSelectScrollEnd);
            optionWrap.addEventListener('click', onSelectClick);

            var select = selectbox.querySelector('.select');
            select.addEventListener('click', function(e){
                e.stopPropagation();
                var thisSelectBox = e.target.closest('.select-box');
                if(!thisSelectBox.classList.contains('active')){
                    selectBoxEl.forEach((sel) => { 
                        sel.classList.remove('active');
                        sel.querySelector('.option-list .option-wrap').scrollTop = 0;
                    });
                    thisSelectBox.classList.add('active');
                }else{
                    thisSelectBox.classList.remove('active');
                    thisSelectBox.querySelector('.option-list .option-wrap').scrollTop = 0;
                }
            });
        });

        const selectOption = document.querySelectorAll('.select-option');
        selectOption.forEach((option) => {
            option.addEventListener('click', function(e){
                var val = e.target.closest('label').querySelector('p').innerText;
                var thisSelectBox = e.target.closest('.select-box');
                var thisSelect = thisSelectBox.querySelector('.select p');
                thisSelect.innerHTML = val;
                thisSelectBox.classList.remove('active');
                thisSelectBox.querySelector('.option-list .option-wrap').scrollTop = 0;
            });
        });
    }*/


    var $btnSitemap = $('.btn-sitemap');
    var $nav = $('.nav');
    const gnbTr = gsap.utils.toArray('.nav .gnb .tr a');
    var $gnbAll = $('.nav .gnb');
    var $snbAll = $('.nav .gnb .snb-wrap');
    $btnSitemap.on('click', function(){
        $(this).toggleClass('active');
        if($(this).hasClass('active')){
            gnbTr.forEach((tr) => {
                gsap.set(tr, {y : '120%', opacity : 0});
            });
            $nav.addClass('active');
            gnbTr.forEach((tr, i) => {
                var delay = (0.1 * i) + 0.45;
                gsap.to(tr, {y : '0', opacity : 1, duration : 0.8}, '-='+delay);
            });
        }else{
            gnbTr.forEach((tr) => {
                gsap.to(tr, {y : '-120%', opacity : 1, duration : 0.8});
            });
            $snbAll.slideUp();
            setTimeout(function(){
                $nav.removeClass('active');
            }, 300);
        }
    });

    var $gnb = $('.nav .gnb .btn-gnb');
    $gnb.on('click', function(e){
        e.preventDefault();
        var link = $(this).attr('href');
        if(link.indexOf('void(0)') < 0){
            location.href = link;
        }else{
            var $thisGnb = $(this).parents('.gnb');
            var $thisSnb = $thisGnb.find('.snb-wrap');
            $thisGnb.toggleClass('on');

            if($thisGnb.hasClass('on')){
                $thisSnb.slideDown();
                $snbAll.not($thisSnb).slideUp();
                $gnbAll.not($thisGnb).removeClass('on');
            }else{
                $thisSnb.slideUp();
                $gnbAll.removeClass('on');
            }
        }
    });

    var $btnFamilySite = $('.btn-family-site');
    var $familySite = $('.family-site .family-site-wrap');
    $btnFamilySite.on('click', function(){
        $(this).toggleClass('active');
        if($(this).hasClass('active')){
            $familySite.addClass('active');
        }else{
            $familySite.removeClass('active');
        }
    });

    $(document).mouseup(function(e){
        if($('.family-site').has(e.target).length === 0){
            $btnFamilySite.removeClass('active');
            $familySite.removeClass('active');
        }
    });


    var $btnTop = $('.btn-top');

    function comInit(){
        $btnTop.css("bottom", footerH + 30);
        var scrt = $(window).scrollTop();
        var sh = $(document).height();
        var wh = $(window).height();

        if(scrt + wh >= sh){
            $btnTop.addClass('active');
        }else{
            $btnTop.removeClass('active');
        }
        
    } comInit();

    $(window).resize(function(){
        var btnTopPosition = footerH + 30;
        $btnTop.css("bottom", btnTopPosition);
    });

    $(document).scroll(function(){
        var scrt = $(window).scrollTop();
        var sh = $(document).height();
        var wh = $(window).height();

        if(scrt + wh >= sh){
            $btnTop.addClass('active');
        }else{
            $btnTop.removeClass('active');
        }
    });

    $btnTop.on('click', function(){
        $('html,body').animate({"scrollTop" : "0"}, 400);
    });

});


function window_info() {
	win_w = $(window).width();
	win_h = $(window).height();
	win_sct = $(window).scrollTop();
	doc_sct = $(document).scrollTop();
}
