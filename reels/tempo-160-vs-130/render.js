const {chromium}=require('playwright');const {spawn}=require('child_process');
(async()=>{const b=await chromium.launch();const pg=await b.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
await pg.goto('file://'+__dirname+'/reel.html');await pg.evaluate(()=>document.fonts.ready);
const FPS=30,D=27,out=process.argv[2]||'reel.mp4';
if(process.argv[3]){for(const s of process.argv[3].split(',')){await pg.evaluate(t=>render(t),+s);await pg.screenshot({path:`shot_${s}.png`});}await b.close();return;}
const ff=spawn('ffmpeg',['-y','-f','image2pipe','-framerate',FPS,'-i','-','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-shortest','-c:v','libx264','-pix_fmt','yuv420p','-profile:v','high','-crf','18','-preset','medium','-c:a','aac','-b:a','128k','-movflags','+faststart',out],{stdio:['pipe','ignore','inherit']});
for(let i=0;i<FPS*D;i++){await pg.evaluate(t=>render(t),i/FPS);const buf=await pg.screenshot({type:'jpeg',quality:95});if(!ff.stdin.write(buf))await new Promise(r=>ff.stdin.once('drain',r));}
ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close();})();
