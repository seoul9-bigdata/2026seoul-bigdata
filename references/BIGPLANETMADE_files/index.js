// 메인

const intro = document.querySelector('.intro');
const wrap = document.getElementById('wrap');
const body = document.querySelector('body');


window.addEventListener('load', function(){
    const logoTxt = gsap.utils.toArray('.logo-txt');
    const introAni = gsap.timeline();
    let introSeen = sessionStorage.getItem('introSeen');

    var $loadingPage = $('#loadingPage');
    var $loadingCount = $loadingPage.find('.percent');

    $({ countNum: $loadingCount.text()}).delay(200).animate({
        countNum: 100,
    },{
        duration: 3000,
        easing:'linear',
        step: function() {
            $loadingCount.text(Math.floor(this.countNum) + '%');
        },
        complete: function() {
            $loadingCount.text(this.countNum + '%');
            setTimeout(function(){
                $loadingPage.fadeOut();

                if(introSeen){
                    introHide();
                }else{
                    introAni.to('.intro', {duration:0, onComplete:function(){
                        logoTxt.forEach(el=>{
                            el.classList.add('active');
                        });
                    }})
                    .to('.intro', {duration:0, onComplete:function(){
                        document.querySelector('.line-circle').classList.add('active');
                    }}, '+=1')
                    .to('.intro', {duration:0, onComplete:function(){
                        document.querySelector('.fill-circle').classList.add('active');
                        document.querySelectorAll('.blank').forEach(el => {
                            el.classList.add('hide');
                        });
                    }}, '+=1')
                    .to('.intro', {duration:0, onComplete:function(){
                        intro.classList.add('intro-ani');
                    }}, '+=1')
                    .to('.intro', {duration:0, onComplete:function(){
                        intro.classList.add('intro-hide');
                    }}, '+=1')
                    .to('.intro', {duration:0, onComplete:function(){
                        document.querySelector('header .logo').classList.add('active');
                        document.querySelector('header .btn-sitemap').classList.add('show');
                    }}, '+=0.5')
                    .to('.intro', {duration:0, onComplete:function(){
                        document.querySelector('.main').classList.add('main-ani');
                    }}, '+=0.5')
                    .to('.intro', {duration:0, onComplete:function(){
                        introHide();
                    }}, '+=2')
                }
                
            }, 800);
        }
    });

    
    

    setSectionHeight();

});


window.addEventListener('resize', function(){
    setSectionHeight();
});

function setSectionHeight(){
    const section = document.querySelectorAll('.main section');
    const sectionbg = document.querySelectorAll('.section-bg section');
    sectionbg.forEach((el, idx) => {
        el.style.height = section[idx + 1].offsetHeight + 'px';
    });
}


function introHide(){
    intro.classList.add('intro-out');

    document.querySelector('header .logo').classList.add('active');
    sessionStorage.setItem('introSeen', 'false');
    document.querySelector('.main').classList.add('main-ani');
    document.querySelector('header .btn-sitemap').classList.add('show');
}

let current_artist_index;
let planet_slide_container = document.querySelector('.planet-slide-container');
let planet_container = planet_slide_container.querySelector('.planet-container');
let planet_wrap = planet_container.querySelector('.planet-wrap');
let planet_box = planet_wrap.querySelectorAll('.planet-box');
let planet_total = planet_box.length;

let previousRealIndex = 0;
let isDragging = false;
let lastRealIndex = -1;

let artist_name_list_wrap = document.querySelector('.artist .name-list-wrap');
let artist_name_list_box = artist_name_list_wrap.querySelector('.name-list-box');
let artist_name_box = artist_name_list_box.querySelectorAll('.name-conts-box');
let artist_name_total = artist_name_box.length;


$(function(){

    gsap.registerPlugin(ScrollTrigger, ScrollSmoother);
    ScrollTrigger.normalizeScroll(true);

    const lenis = new Lenis();
    lenis.on('scroll', ScrollTrigger.update);

    gsap.ticker.add((time)=>{
        lenis.raf(time * 1000);
    })

    gsap.ticker.lagSmoothing(0);

    let mm = gsap.matchMedia();

    /* section visual */
    const visualAniOption = {
        scrollTrigger : {
            trigger : '.main .visual',
            start : 'top top',
            end : '+=180%',
            scrub : 1,
            pin : true,
            invalidateOnRefresh: true,
        }
    };
    const visualAni = gsap.timeline(visualAniOption);
    const mainPlanet = document.querySelector('.main-planet');
    const mainPlanetShadow = mainPlanet.querySelector('.shadow');
    const mainPlanetSurface = mainPlanet.querySelector('.surface');
    const mainPlanetSurfaceWrap = mainPlanet.querySelector('.surface-wrap');
    const mainPlanetInset = mainPlanet.querySelector('.inset');
    const mainPlanetInset2 = mainPlanet.querySelector('.inset-2');
    const basicPlanet = document.querySelector('.basic-planet');
    const basicPlanetShadow = basicPlanet.querySelector('.shadow');

    const visualContsWrap = document.querySelector('.visual-conts-wrap');
    const visualTitle = visualContsWrap.querySelector('.title-wrap');
    const visualConts = visualContsWrap.querySelector('.conts-wrap');

    const storyContsWrap = document.querySelector('.story-conts-wrap');
    const storyContsBox = storyContsWrap.querySelector('.story-conts-box');
    const storyContsTitle = storyContsBox.querySelector('.tlt span');
    const storyContsRow = gsap.utils.toArray('.story-conts-box .conts .row');

    const visualLight = document.querySelector('.visual .light');
    const visualLightEl = visualLight.querySelector('span');
    setVisualLight();
    
    function setVisualLight(){
        let visualLightH = visualLightEl.offsetHeight;
        var visualLightTop = (basicPlanet.getBoundingClientRect().top - (visualLightH * 0.45));
        visualLight.style.top = visualLightTop + 'px';
    }

    window.addEventListener('resize', function(){
        //setVisualLight();
    });

    visualAni.to(visualLight, {duration : 0, onComplete : function(){
        let tl = gsap.timeline({repeat:1, defaults : {ease : 'power1.inOut'}});
        tl.to(visualLight, {opacity : 0, duration : 0.6, delay : 2})
        .to(visualLight, {opacity : 1, duration : 0.6})
        .to(visualLight, {opacity : 0, duration : 0.6});
    }})

    mm.add("(min-width: 1501px)", () => {
        gsap.set(mainPlanet, {left:'-10%', top:'48%', width:'1500', height:'1500'});
        gsap.set(mainPlanetShadow, {boxShadow:'inset 375px -1000px 150px 5px rgba(0, 0, 0, 1)'});
        gsap.set(mainPlanetInset, {boxShadow:'inset -50px 20px 70px 5px rgb(60, 7, 143, 0.48)'});
        gsap.set(mainPlanetInset2, {boxShadow:'inset -50px 20px 70px -10px rgb(0, 0, 0, 1)'});
        gsap.set(basicPlanetShadow, {boxShadow:'inset 190px -180px 80px 3px rgb(0, 0, 0, 1)'});

        visualAni.to(mainPlanet, {left:'50%', top:'50%', x:'-50%', y:'-50%', width:'550', height:'550'}, '<')
        .to(mainPlanetShadow, {boxShadow : 'inset 135px -85px 80px -20px rgba(0,0,0,0.95)'}, '<')
        .to(mainPlanetInset, {boxShadow : 'inset -35px 35px 60px -34px rgba(228,153,241,0.45)'}, '<')
        .to(mainPlanetInset2, {boxShadow : 'inset -80px 49px 30px -75px rgba(0,0,0,0.8)'}, '<')
        .to(basicPlanetShadow, {boxShadow : 'inset 190px -400px 80px 3px rgba(0,0,0,1)'}, '<');
    });

    mm.add("(max-width: 1500px) and (min-width: 1025px)", () => {
        gsap.set(mainPlanet, {left:'-10%', top:'48%', width:'1000', height:'1000'});
        gsap.set(mainPlanetShadow, {boxShadow:'inset 365px -590px 170px 5px rgba(0, 0, 0, 1)'});
        gsap.set(mainPlanetInset, {boxShadow:'inset -40px 5px 40px -5px rgb(60, 7, 143, 0.48)'});
        gsap.set(mainPlanetInset2, {boxShadow:'inset -40px 15px 60px -8px rgb(0, 0, 0, 1)'});
        gsap.set(basicPlanetShadow, {boxShadow:'inset 120px -130px 70px 3px rgb(0, 0, 0, 1)'});

        visualAni.to(mainPlanet, {left:'50%', top:'50%', x:'-50%', y:'-50%', width:'420', height:'420'}, '<')
        .to(mainPlanetShadow, {boxShadow : 'inset 115px -110px 90px -20px rgba(0,0,0,0.95)'}, '<')
        .to(mainPlanetInset, {boxShadow : 'inset -35px 35px 60px -34px rgba(228,153,241,0.45)'}, '<')
        .to(mainPlanetInset2, {boxShadow : 'inset -80px 49px 30px -75px rgba(0,0,0,0.8)'}, '<')
        .to(basicPlanetShadow, {boxShadow : 'inset 160px -310px 70px 3px rgba(0,0,0,1)'}, '<');
    });

    mm.add("(max-width: 1024px) and (min-width: 769px)", () => {
        gsap.set(mainPlanet, {left:'-20%', top:'55%', width:'900', height:'900'});
        gsap.set(mainPlanetShadow, {boxShadow:'inset 285px -520px 150px 5px rgba(0, 0, 0, 1)'});
        gsap.set(mainPlanetInset, {boxShadow:'inset -25px -2px 40px -5px rgb(60, 7, 143, 0.48)'});
        gsap.set(mainPlanetInset2, {boxShadow:'inset -40px 5px 55px -5px rgb(0, 0, 0, 1)'});
        gsap.set(basicPlanetShadow, {boxShadow:'inset 120px -130px 70px 3px rgb(0, 0, 0, 1)'});

        visualAni.to(mainPlanet, {left:'50%', top:'50%', x:'-50%', y:'-50%', width:'400', height:'400'}, '<')
        .to(mainPlanetShadow, {boxShadow : 'inset 110px -100px 90px -20px rgba(0,0,0,0.95)'}, '<')
        .to(mainPlanetInset, {boxShadow : 'inset -45px 35px 50px -35px rgba(228,153,241,0.45)'}, '<')
        .to(mainPlanetInset2, {boxShadow : 'inset -96px 40px 30px -80px rgba(0,0,0,0.8)'}, '<')
        .to(basicPlanetShadow, {boxShadow : 'inset 160px -310px 70px 3px rgba(0,0,0,1)'}, '<');
    });

    mm.add("(max-width: 768px) and (min-width: 649px)", () => {
        gsap.set(mainPlanet, {left:'-20%', top:'55%', width:'750', height:'750'});
        gsap.set(mainPlanetShadow, {boxShadow:'inset 255px -370px 110px -15px rgba(0, 0, 0, 1)'});
        gsap.set(mainPlanetInset, {boxShadow:'inset -50px -2px 30px -15px rgb(60, 7, 143, 0.48)'});
        gsap.set(mainPlanetInset2, {boxShadow:'inset -20px 12px 40px -6px rgb(0, 0, 0, 1)'});
        gsap.set(basicPlanetShadow, {boxShadow:'inset 90px -120px 70px 3px rgb(0, 0, 0, 1)'});

        visualAni.to(mainPlanet, {left:'50%', top:'50%', x:'-50%', y:'-50%', width:'400', height:'400'}, '<')
        .to(mainPlanetShadow, {boxShadow : 'inset 110px -90px 80px -23px rgba(0,0,0,0.95)'}, '<')
        .to(mainPlanetInset, {boxShadow : 'inset -45px 35px 50px -35px rgba(228,153,241,0.45)'}, '<')
        .to(mainPlanetInset2, {boxShadow : 'inset -108px 33px 30px -90px rgba(0,0,0,0.8)'}, '<')
        .to(basicPlanetShadow, {boxShadow : 'inset 110px -320px 70px 3px rgba(0,0,0,1)'}, '<');
    });

    mm.add("(max-width: 648px) and (min-width: 481px)", () => {
        gsap.set(mainPlanet, {left:'-30%', top:'55%', width:'550', height:'550'});
        gsap.set(mainPlanetShadow, {boxShadow:'inset 205px -290px 90px -10px rgba(0, 0, 0, 1)'});
        gsap.set(mainPlanetInset, {boxShadow:'inset -40px 8px 20px -18px rgb(60, 7, 143, 0.48)'});
        gsap.set(mainPlanetInset2, {boxShadow:'inset -30px -25px 40px -5px rgb(0, 0, 0, 1)'});
        gsap.set(basicPlanetShadow, {boxShadow:'inset 86px -100px 50px 3px rgb(0, 0, 0, 1)'});

        visualAni.to(mainPlanet, {left:'50%', top:'50%', x:'-50%', y:'-50%', width:'320', height:'320'}, '<')
        .to(mainPlanetShadow, {boxShadow : 'inset 90px -80px 60px -20px rgba(0,0,0,0.95)'}, '<')
        .to(mainPlanetInset, {boxShadow : 'inset -50px 25px 40px -38px rgba(228,153,241,0.45)'}, '<')
        .to(mainPlanetInset2, {boxShadow : 'inset -120px 15px 35px -110px rgba(0,0,0,0.8)'}, '<')
        .to(basicPlanetShadow, {boxShadow : 'inset 125px -250px 50px 3px rgba(0,0,0,1)'}, '<');
    });

    mm.add("(max-width: 480px)", () => {
        gsap.set(mainPlanet, {left:'-30%', top:'55%', width:'400', height:'400'});
        gsap.set(mainPlanetShadow, {boxShadow:'inset 125px -180px 80px -10px rgba(0, 0, 0, 1)'});
        gsap.set(mainPlanetInset, {boxShadow:'inset -30px 28px 30px -22px rgb(60, 7, 143, 0.48)'});
        gsap.set(mainPlanetInset2, {boxShadow:'inset -30px -8px 36px -10px rgb(0, 0, 0, 1)'});
        gsap.set(basicPlanetShadow, {boxShadow:'inset 75px -75px 55px 2px rgb(0, 0, 0, 1)'});

        visualAni.to(mainPlanet, {left:'50%', top:'50%', x:'-50%', y:'-50%', width:'250', height:'250'}, '<')
        .to(mainPlanetShadow, {boxShadow : 'inset 85px -70px 55px -20px rgba(0,0,0,0.95)'}, '<')
        .to(mainPlanetInset, {boxShadow : 'inset -60px 45px 33px -43px rgba(228,153,241,0.45)'}, '<')
        .to(mainPlanetInset2, {boxShadow : 'inset -105px 5px 25px -83px rgba(0,0,0,0.8)'}, '<')
        .to(basicPlanetShadow, {boxShadow : 'inset 95px -185px 55px 2px rgba(0,0,0,1)'}, '<');
    });

    visualAni.to(mainPlanetSurfaceWrap, {boxShadow : '0px -4px 25px 5px rgba(197,183,225,0.5)'}, '<')
    .to(basicPlanet, {filter : 'blur(3px)', scale : '0.7'}, '<')
    .to(visualTitle, {opacity : 0}, '<')
    .to(visualConts, {opacity : 0}, '<');

    visualAni.to(storyContsWrap, {visibility : 'visible'}, '<')
    .to(storyContsTitle, {y : '0', duration : 0.7, ease : 'power1.inOut'}, '<');
    
    storyContsRow.forEach((el, i) => {
        var thisConts = el.querySelector('span');
        visualAni.to(thisConts, {y : '0', duration : 0.7, ease : 'power1.inOut'}, '<');
    });


    /*visualAni.to(mainPlanet, {left : '50%', x : '-50%', top : '50%', y : '-50%', width : '550', height : '550'})
    .to(mainPlanetShadow, {boxShadow : 'inset 135px -85px 80px -20px rgba(0,0,0,0.95)'}, '<')
    .to(mainPlanetSurface, {scale : '1.01'}, '<')
    .to(mainPlanetSurfaceWrap, {boxShadow : '0px -4px 25px 5px rgba(197,183,225,0.5)'}, '<')
    .to(mainPlanetInset, {boxShadow : 'inset -35px 35px 60px -34px rgba(228,153,241,0.45)'}, '<')
    .to(mainPlanetInset2, {boxShadow : 'inset -80px 49px 30px -75px rgba(0,0,0,0.8)'}, '<')
    .to(basicPlanetShadow, {boxShadow : 'inset 190px -400px 80px 3px rgba(0,0,0,1)'}, '<')
    .to(basicPlanet, {filter : 'blur(3px)', scale : '0.7'}, '<')
    .to(visualTitle, {opacity : 0}, '<')
    .to(visualConts, {opacity : 0}, '<');

    visualAni.to(storyContsWrap, {visibility : 'visible'}, '<')
    .to(storyContsTitle, {y : '0', duration : 0.7, ease : 'power1.inOut'}, '<');
    
    storyContsRow.forEach((el, i) => {
        var thisConts = el.querySelector('span');
        visualAni.to(thisConts, {y : '0', duration : 0.7, ease : 'power1.inOut'}, '<');
    });*/


    /* section artist */
    var $allArtist = $('.artist .artist-list li');
    $allArtist.each(function(){
        var artistTxt = $(this).find('span').text();
        if(artistTxt.length > 8){
            $(this).addClass('long');
        }
    });
    let loopLen = $allArtist.length * 2;
    var $artistProfile = new Swiper('.artist .artist-profile-img', {
        //parallax: true,
        effect : 'fade',
        loop: true,
        speed : 1500,
        observer: true,
        observeParents: true,
        loopedSlides : loopLen,
        touchRatio : 0,
    });

    var $artistConts = new Swiper('.artist .artist-conts-container', {
        loop: true,
        slidesPerView: 1,
        speed : 1500,
        observer: true,
        observeParents: true,
        loopedSlides : loopLen,
        touchRatio : 0,
        effect : 'fade'
    });

    planet_box.forEach((el) => {
        var prevClone = $(el).clone().addClass('duplicate-prev');
        el.classList.add('duplicate-next');
        $(planet_wrap).prepend(prevClone);
    });

    var $artistList = new Swiper('.artist .thumb-box', {
        loop: true,
        slidesPerView: 3,
        spaceBetween: 16,
        centeredSlides: true,
        speed : 1500,
        slideToClickedSlide : true,
        observer: true,
        observeParents: true,
        loopedSlides : loopLen,
        arrows : false,
        loopAdditionalSlides : 1,
        thumbs : {
            swiper : $artistProfile
        },
        on : {
            touchStart : function() {
                isDragging = true;
            },
            touchEnd : function() {
                isDragging = false;
            },
            slideChange : function() {
                const swiper = this;
                const maxWait = 10;
                let frameCount = 0;

                function waitForIndexChange() {
                    if (swiper.realIndex !== lastRealIndex) {
                        const direction = getLoopDirection(
                            lastRealIndex,
                            swiper.realIndex,
                            swiper.slides.length - swiper.loopedSlides * 2
                        );
                        onSlideChanged(swiper.realIndex, direction, lastRealIndex);
                        lastRealIndex = swiper.realIndex;
                    } else if (frameCount < maxWait) {
                        frameCount++;
                        requestAnimationFrame(waitForIndexChange);
                    }
                }

                requestAnimationFrame(waitForIndexChange);
            }
        }
    });

    function onSlideChanged(index, dir, prevIndex){
        const tl = gsap.timeline();

        const prevCurrentBox = $(`.planet-wrap .planet-box[data-index="${prevIndex}"].current`);
        const prevCurrentNameBox = $(`.artist .name-list-wrap .name-list-box .name-conts-box[data-index="${prevIndex}"].current`);

        if(prevCurrentBox.length){
            const xVal = (dir === 'next') ? '-100%' : '100%';
            const op = (dir === 'next') ? '100% 100%' : '0% 100%';
            const planetX = (dir === 'next') ? '-100%' : '100%';
            const prevCurrentPlanet = prevCurrentBox.find('.artist-planet');

            tl.to(prevCurrentBox, {
                x: xVal,
                duration: 1.5,
                onComplete: function () {
                    prevCurrentBox.remove();
                }
            });
            tl.to(prevCurrentNameBox, {
                visibility : 'hidden',
                opacity : '0',
                duration: 0,
                onComplete: function () {
                    prevCurrentNameBox.remove();
                }
            }, '<');
            tl.to(prevCurrentPlanet, {
                x: planetX,
                scale: 0.3,
                opacity: 1,
                visibility: 'hidden',
                transformOrigin: op
            }, '<-=0.3');
        }

        const currentBox = $(`.planet-wrap .planet-box.duplicate-${dir}[data-index="${index}"]`);
        const clone = currentBox.last().clone();
        const currentPlanet = currentBox.find('.artist-planet');
        currentBox.addClass('current');

        const currentNameBox = $(`.artist .name-list-wrap .name-list-box .name-conts-box[data-index="${index}"]`);
        const nameBoxClone = currentNameBox.last().clone();
        const currentName = currentNameBox.find('.name-inner span');
        currentNameBox.addClass('current');

        gsap.set(currentPlanet, { x: '100%', scale: 0.3, opacity: 1, visibility: 'hidden' });

        tl.to(currentBox, {
            x: 0,
            duration: 1.2,
            onComplete: function () {
                if (dir === 'next') {
                    $('.planet-wrap').append(clone);
                } else {
                    $('.planet-wrap').prepend(clone);
                }
            }
        }, '<');

        tl.to(currentNameBox, {
            visibility : 'visible',
            opacity : '1',
            duration: 1.2,
            onComplete: function () {
                $(artist_name_list_box).append(nameBoxClone);
            }
        }, '<');

        tl.to(currentPlanet, {
            x: '0%',
            scale: 1,
            opacity: 1,
            visibility: 'visible',
            duration: 0.5
        }, '<-=0.5');

        tl.to(currentName, {
            y : '0%',
            opacity : '1',
            duration: 0.5
        }, '<-=0.5');
    }

    function getLoopDirection(prev, curr, total) {
        if (prev === null) return 'next';
        if (curr === 0 && prev === total - 1) return 'next';
        if (curr === total - 1 && prev === 0) return 'prev';
        return curr > prev ? 'next' : 'prev';
    }

    /*var $artistPlanet = new Swiper('.artist .planet-container', {
        loop: true,
        slidesPerView: 1,
        speed : 1500,
        observer: true,
        observeParents: true,
        loopedSlides : loopLen,
        touchRatio : 0,
        waitForTransition : false,
    });*/


    /*var $artistName = new Swiper('.artist .name-list-wrap', {
        loop: true,
        slidesPerView: 1,
        speed : 1500,
        observer: true,
        observeParents: true,
        loopedSlides : loopLen,
        effect : 'fade',
        touchRatio : 0,
        thumbs : {
            swiper : $artistConts
        }
    });*/

    /*$artistList.controller.control = $artistPlanet;
    $artistPlanet.controller.control = $artistList;

    $artistProfile.controller.control = $artistName;
    $artistName.controller.control = $artistProfile;*/

    $artistProfile.controller.control = $artistConts;

    const artistAniOption = {
        scrollTrigger : {
            trigger : 'section.artist',
            start : 'top-=30%',
        }
    };
    const artistAni = gsap.timeline(artistAniOption);
    const artistTitle = document.querySelector('.artist .sec-title h3');
    const artistTitleConts = document.querySelector('.artist .sec-title .conts');
    const artistConts = document.querySelector('.artist .artist-slide-wrap');
    const artistButton = document.querySelector('.artist .sec-title .button-box a');

    artistAni.to(artistTitle, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'})
    .to(artistTitleConts, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '-=0.3')
    .to(artistConts, { opacity : 1, duration : 0.5, ease : 'power1.inOut'}, '-=0.3')
    .to(artistButton, { y : '0', opacity : 1, duration : 0.5, ease : 'power1.inOut'}, '<-=0.3');

    /*var $nameThumb = $('.artist .thumb-box .artist-list li');
    $nameThumb.on('click', function(){
        var idx = $(this).data('swiper-slide-index');
        $artistList.slideTo(idx, 0);
    });*/





    /* section discograph */
    let discographSlide;

    function initializeDiscograph(){
        discographSlide = new Swiper('.discograph .discograph-container', {
            loop : true,
            slidesPerView : 3.5,
            centeredSlides : true,
            effect : "coverflow",
            coverflowEffect : {
                rotate : 40,
                slideShadows : false,
                depth : 250,
                strech : 1,
            },
            grabCursor: true,
            pagination : {
                el: '.swiper-pagination',
            },
            breakpoints : {
                0 : {
                    slidesPerView : 2.5,
                    coverflowEffect : {
                        rotate : 40,
                        depth : 200,
                        stretch : 5,
                    }
                },
                648 : {
                    slidesPerView : 3.5,
                    coverflowEffect : {
                        rotate : 30,
                        depth : 160,
                        stretch : 5,
                    }
                },
                768 : {
                    coverflowEffect : {
                        rotate : 30,
                        depth : 200,
                        stretch : 2,
                    }
                },
                1024 : {
                    coverflowEffect : {
                        rotate : 30,
                        depth : 230,
                        stretch : 3,
                    }
                },
                1280 : {
                    coverflowEffect : {
                        depth : 250
                    }
                }
            }
        });
    }

    initializeDiscograph();

    window.addEventListener('resize', function(event) {
        discographSlide.destroy();
        initializeDiscograph();
    }, true);

    const discographAniOption = {
        scrollTrigger : {
            trigger : 'section.discograph',
            start : 'top-=50%',
            onEnter : () => {
                document.querySelector('.discograph').classList.add('active');
            }
        }
    };
    const discographAni = gsap.timeline(discographAniOption);
    const discographTitle = document.querySelector('.discograph .sec-title h3');
    const discographTitleConts = document.querySelector('.discograph .sec-title .conts');
    const discographViewMore = document.querySelector('.discograph .sec-title .view-more');
    const discographConts = document.querySelector('.discograph .discograph-conts-wrap');

    discographAni
    .to(discographTitle, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'})
    .to(discographTitleConts, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '-=0.3')
    .to(discographViewMore, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '-=0.3')
    .to(discographConts, { opacity : 1, duration : 0.5, ease : 'power1.inOut'}, '-=0.3');







    /* section video */
    var videoContsWrap = document.querySelector('.video .video-conts-wrap');
    var videoFrame = document.querySelector('.video .frame');
    var $videoList = new Swiper('.video .video-wrap', {
        loop: true,
        slidesPerView: 1,
        spaceBetween: 0,
        centeredSlides: true,
        speed : 1500,
        slideToClickedSlide : false,
        observer: true,
        observeParents: true,
        loopedSlides : 2,
        initialSlide : 0,
        touchRatio : 1,
        navigation : {
            nextEl: '.nav-button-next',
            prevEl: '.nav-button-prev',
        },
        on : {
            init : function(e){
                videoSlideCount(e);
                videoContsWrap.classList.add('init');
            },
            slideChangeTransitionStart : function(){
                videoFrame.classList.add('expand');
            },
            slideChangeTransitionEnd : function(){
                videoFrame.classList.remove('expand');
            }
        }
    });

    function videoSlideCount(slide){
        let currentSlide = geSlideDataIndex(slide);
        let total = $('.video .video-box').not('.swiper-slide-duplicate').length;
        var html = "";
        html += "<span class='current'>"+currentSlide+"</span>";
        html += "<span> / </span>";
        html += "<span class='total'>"+total+"</span>";
        document.querySelector('.video .video-conts-wrap .slide-navigation .counter').innerHTML = html;
        if(currentSlide != 1){
            videoContsWrap.classList.remove('init');
            videoContsWrap.classList.remove('ani');
        }
    }

    function geSlideDataIndex(swipe) {
        let activeIndex = swipe.activeIndex;
        let slidesLen = $('.video .video-box').not('.swiper-slide-duplicate').length;
        if(swipe.params.loop){
            switch(swipe.activeIndex){
                case 1 :
                    activeIndex = slidesLen;
                    break;
                case slidesLen+2 : 
                    activeIndex = 1;
                    break;
                default:
                    --activeIndex;
            }
        }
        return  activeIndex;
    }

    $videoList.on('slideChange afterInit init', function(){
        videoSlideCount(this);
    });

    const videoAniOption = {
        scrollTrigger : {
            trigger : 'section.video',
            start : 'top-=50%',
            onEnter : () => {
                videoContsWrap.classList.add('ani');
            }
        }
    };
    const videoAni = gsap.timeline(videoAniOption);
    const videoTitle = document.querySelector('.video .sec-title h3');
    const videoTitleConts = document.querySelector('.video .sec-title .conts');
    const videoButton = document.querySelector('.video .sec-title .button-box a');

    videoAni
    .to(videoTitle, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'})
    .to(videoTitleConts, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '-=0.3')
    .to(videoButton, { y : '0', opacity : 1, duration : 0.5, ease : 'power1.inOut'}, '<-=0.3');

    const btnVideoPlay = document.querySelectorAll('.btn-video-play');
    const videoAll = document.querySelectorAll('.video iframe');
    btnVideoPlay.forEach((btn) => {
        btn.addEventListener('click', (el) => {
            var videoId = el.target.dataset.id;
            var contsWrap = el.target.parentElement.parentElement;
            var thumbWrap = contsWrap.querySelector('.thumb-wrap');
            var iframeBox = contsWrap.querySelector('.iframe-box');
            var html = '<span><iframe src="https://www.youtube.com/embed/'+videoId+'?enablejsapi=1&version=3&playerapiid=ytplayer" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></span>';
            iframeBox.innerHTML = html;
            var iframe = contsWrap.querySelector('.iframe-box iframe');

            iframe.addEventListener('load', function(){
                iframe.contentWindow.postMessage('{"event":"command","func":"playVideo","args":""}','*');
                thumbWrap.classList.add('hide');
            });
        });
    });

    $videoList.on('slideChange', function(e){
        var iframeAll = document.querySelectorAll('.video .iframe-box iframe');
        iframeAll.forEach((el) => {
            var contsWrap = el.parentElement.parentElement.parentElement;
            var thumbWrap = contsWrap.querySelector('.thumb-wrap');
            var iframeBox = contsWrap.querySelector('.iframe-box');

            thumbWrap.classList.remove('hide');
            el.contentWindow.postMessage('{"event":"command","func":"stopVideo","args":""}','*');
            iframeBox.innerHTML = '';
        });
    });





    /* section news */
    const newsAniOption = {
        scrollTrigger : {
            trigger : 'section.news',
            start : 'top-=50%'
        }
    };
    const newsAni = gsap.timeline(newsAniOption);
    const newsItems = document.querySelectorAll('.news ul.list-tb li.tr');
    const thumbItems = document.querySelectorAll('.news .bbs-thumbnail');

    newsItems.forEach((item) => {
        const thisThumbnail = item.querySelector('.bbs-thumbnail');
        const thisThumbnailBounds = thisThumbnail.getBoundingClientRect();
        const itemBounds = item.getBoundingClientRect();

        const onMouseEnter = () => {
            gsap.to(thisThumbnail, { opacity : 1, duration : 0.2 });
        };

        const onMouseLeave = () => {
            gsap.to(thisThumbnail, { opacity : 0, duration : 0.2 });
        };

        const onMouseMove = ({ x, y }) => {
			let yOffset = itemBounds.top / thisThumbnailBounds.height;
			gsap.to(thumbItems, {
				x: Math.abs(x - itemBounds.left) ,
				transformOrigin: "center",
			});
		  };

        item.addEventListener("mouseenter", onMouseEnter);
        item.addEventListener("mouseleave", onMouseLeave);
        item.addEventListener("mousemove", onMouseMove);
    });

    const newsTitle = document.querySelector('.news .sec-title h3');
    const newsTitleConts = document.querySelector('.news .sec-title .conts');
    const newsConts = document.querySelector('.news .news-conts-wrap');
    const newsButtonWrap = document.querySelector('.news .news-conts-wrap .button-wrap');

    newsAni
    .to(newsTitle, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'})
    .to(newsTitleConts, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '-=0.3')
    .to(newsConts, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '-=0.3')
    .to(newsButtonWrap, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '-=0.3');




    /* section outro */
    const outroAniOption = {
        scrollTrigger : {
            trigger : 'section.outro',
            start : 'top-=30%',
        }
    };
    const outroAni = gsap.timeline(outroAniOption);
    const outroMainPlanet = document.querySelector('.outro .outro-main-planet');
    const outroTitle = document.querySelector('.outro .sec-title h3');
    const outroTitleConts = document.querySelector('.outro .sec-title .conts');
    const outroButtonWrap = document.querySelector('.outro .outro-conts-wrap .button-wrap');
    const outroLight = document.querySelectorAll('.outro .light');
    const outroLight1 = document.querySelector('.outro .light-1');
    const outroLight2 = document.querySelector('.outro .light-2');
    setOutroLight();

    outroAni.to(outroMainPlanet, { opacity : 1, y : '0%', duration : 2 })
    .to(outroLight1, {duration:0, onComplete:function(){
        outroLight1.classList.add('ani');
    }})
    .to(outroLight2, {duration:0, onComplete:function(){
        outroLight2.classList.add('ani');
    }}, '<')
    .to(outroMainPlanet, { keyframes : {
        "0%" : { boxShadow : '-5px -10px 30px 5px rgba(255, 135, 253, 0.4)' },
        "25%" : { boxShadow : '-10px -17px 30px 5px rgba(255, 143, 253, 0.15)' },
        "50%" : { boxShadow : '-10px -30px 30px 5px rgba(255, 129, 253, 0.1)' },
        "75%" : { boxShadow : '-10px -17px 30px 5px rgba(252, 132, 250, 0.15)' },
        "100%" : { boxShadow : '-5px -8px 30px 5px rgba(255, 147, 253, 0.4)' }
    }, duration : 7, ease : 'none' }, '<-=2')
    .to(outroTitle, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '<+=1.5')
    .to(outroTitleConts, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '<')
    .to(outroButtonWrap, { y : '0', opacity : 1, duration : 0.6, ease : 'power1.inOut'}, '<');

    function setOutroLight(){
        outroLight.forEach((el) => {
            let outroLightH = el.offsetHeight;
            var lightTop = (outroLightH - (outroLightH * 0.24)) * -1;
            el.style.top = lightTop + 'px';
        });        
    }

    window.addEventListener('resize', function(){
        setOutroLight();
    });


    window.addEventListener('resize', function(event) {
        ScrollTrigger.update
    }, true);
    ScrollTrigger.refresh();
    ScrollTrigger.config({ ignoreMobileResize: true });


    window.addEventListener('scroll', function(){
        const scroll = document.querySelector('.scroll');
        var scrt = document.querySelector('html').scrollTop;
        if(scrt > 300){
            scroll.classList.add('hide');
        }else{
            scroll.classList.remove('hide');
        }
    });

    

});