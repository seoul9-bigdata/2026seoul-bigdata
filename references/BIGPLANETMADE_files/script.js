// 공통
import {normalizeColor} from './gradient.js';
import {MiniGl} from './gradient.js';
import {e} from './gradient.js';
import {Gradient} from './gradient.js';


window.onload = function(){
    const introBg = document.getElementById('intro-bg');
    if(introBg != null){
        /*var gradient = new Gradient();
        gradient.initGradient("#intro-bg");*/
        starFieldinit();
    }

    const contents = document.querySelector('.contents');
    if(contents != null){
        document.querySelector('header .logo').classList.add('active');
        document.querySelector('header .btn-sitemap').classList.add('show');
    }

    if(mobileIs){
        document.querySelector('.contents').classList.add('mo');
    }

    const moreContsBox = document.querySelectorAll('.more-conts-box');
    if(moreContsBox.length > 0){
        moreContsBox.forEach((el) => {
            const contsBox = el.querySelector('.conts-box');
            const btntMore = el.querySelector('.btn-conts-more');
            let boxHeight = contsBox.clientHeight;
            let originHeight = contsBox.querySelector('.conts').offsetHeight;

            if(boxHeight < originHeight){
                btntMore.classList.add('active');
            }else{
                btntMore.classList.remove('active');
            }

            btntMore.addEventListener('click', function(e){
                var btn = e.target;
                var thisContsBox = btn.parentElement.querySelector('.conts-box');

                if(!thisContsBox.classList.contains('open')){
                    btn.innerHTML = '< CLOSE';
                    thisContsBox.classList.add('open');
                }else{
                    btn.innerHTML = 'MORE >';
                    thisContsBox.classList.remove('open');
                }
            });
        });
    }


    $('input[type=checkbox]#agree-all').on('change', function(){
        var $agreeWrap = $(this).parents('.all-check-wrap').siblings('.agree-wrap');
        var $allAgree = $agreeWrap.find('input[type=checkbox]');
        if($(this).is(":checked")){
            $allAgree.each(function(){
               $(this).prop('checked',true);
            });
        }else{
            $allAgree.each(function(){
                $(this).prop('checked',false);
             })
        }
    });


    let comAniEl = gsap.utils.toArray('.com-ani');
    if(comAniEl.length > 0){
        comAniEl.forEach((el) => {
            ScrollTrigger.create({
                trigger : el,
                onEnter : () => {
                    el.classList.add('animation');
                }
            });
        });
    }

    let depthCategory = document.querySelector('.depth-category-wrap');
    if(depthCategory != null){
        let depthCategoryEl = depthCategory.querySelectorAll('ul.depth-category li');
        let depthId = document.querySelector('.contents').dataset.depth;
        let left = 0;
        if(typeof depthId !== "undefined"){
            depthCategoryEl.forEach((el) => {
                var id = el.dataset.id;
                if(id == depthId){
                    el.classList.add('on');
                    left = el.getBoundingClientRect().left - 20;
                    console.log(el.getBoundingClientRect().left);
                }else{
                    el.classList.remove('on');
                }
            });
            left = (left < 0) ? 0 : left;
            let categoryBox = depthCategory.querySelector('.category-box');
            categoryBox.scrollLeft = left;
        }
    }
    
}


$(function(){
    
});
