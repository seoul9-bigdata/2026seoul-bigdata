var canvasArray = [];
var stars = [];
var starsArray = [];
var quantity = 1000;
var screenH;
var screenW;
var fps = 20;
var sizeOption = 3;
var durationOption = 200;

window.addEventListener('load', function(){
    var canvasEl = document.querySelectorAll('.stars');

    function updateStars(){
        screenH = $(window).height();
        screenW = $(window).width();

        canvasEl.forEach((el) => {
            stars = [];
            var canvas = el.getContext("2d");
            canvasArray.push(canvas);
            
            $(el).attr('height', screenH);
            $(el).attr('width', screenW);

            var w = window.innerWidth;
            if((w <= 1024) && (w > 768)){
                quantity = 600;
                sizeOption = 4;
                durationOption = 150;
            }else if((w <= 768) && (w > 480)){
                quantity = 400;
                durationOption = 120;
                sizeOption = 5;
            }else if((w <= 480)){
                quantity = 220;
                sizeOption = 10;
                durationOption = 100;
            }

            for (let i = 0; i < quantity; i++) {
                var positionX = window.innerWidth * Math.random();
                var positionY = window.innerHeight * Math.random();
                var offset    = Math.random() * 100;
                var duration  = Math.random() * 50 + 50;
                var size      = Math.random() * 2;
                stars.push(new Star(canvas, positionX, positionY, offset, duration, size));
            }
            starsArray.push(stars);
        });

        canvasArray.forEach((el, idx) => {
            setInterval(function(){
                renderFrame(el, starsArray[idx]);
            }, 1000 / fps);
        });
    }

    if(!mobileIs){
        updateStars();
    }

    window.addEventListener('resize', function(){
        if(!mobileIs){
            canvasArray.forEach((el, idx) => {
                setInterval(function(){
                    renderFrame(el, starsArray[idx]);
                }, 1000 / fps);
            });
        }
    });

});




function Star (canvas, x, y, offset, duration = durationOption, size = 2) {
  //constructor
  this.x            = x;
  this.y            = y;
  this.duration     = duration;
  this.offset       = offset;
  this.size         = size;
  this.timer        = offset % duration;
  
  //functions
  this.draw = function () {
    //Calculate animations
    if (this.timer > this.duration) {
      this.timer = 0;
    }
    this.timer += 1;
    
    //Calculate
    var framesize = Math.abs((this.timer / this.duration) - 0.3) * this.size + this.size/sizeOption;
    
    //Update element
    canvas.beginPath();
    canvas.arc(this.x, this.y, framesize, 0, Math.PI * 2, false);
    canvas.fillStyle = "white";
    canvas.fill();
  }
}

function renderFrame (canvas, star) {
    canvas.clearRect(0, 0, screenW, screenH);
    for(let i = 0; i < quantity; i++){
        star[i].draw();
    }
}