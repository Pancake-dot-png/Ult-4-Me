// Offline renderer integration test. No screen capture, connection or device IPC.
const {app,BrowserWindow,ipcMain,session,nativeImage}=require('electron');
const path=require('path');
const fs=require('fs');
const {Config,REGIONS}=require('../app/src/config');
const {validateOptions}=require('../app/src/detection-options');
const root=path.resolve(__dirname,'..');
app.setPath('userData',path.join(root,'build/smoke-profile'));
const config=new Config(path.join(root,'build/smoke-unused.json'));
config.detectables={Example:{filename:'apply_mercy_heal.png',points:10,type:0,region:'Receive Heal',threshold:.7}};
let saved=null;
let savedThreshold=null;
for(const [channel,fn] of Object.entries({
  'get-config':()=>({settings:config.settings,detectables:config.detectables}),
  'set-config':(_,key,value)=>{config.settings[key]=value;},
  'get-local-ip':()=>'', 'is-vision-running':()=>false,'get-toys':()=>({}),
  'start-vision':()=>({ok:false,error:'Screen capture disabled in offline smoke test'}),
  'get-mute-status':()=>({muted:false,key:'Delete',url:''}),
  'get-monitor-count':()=>1,
  'get-zones':()=>({regions:REGIONS,baseW:1920,baseH:1080,disabledZones:[]}),
  'get-debug-config':()=>({detectables:config.detectables,templatesDir:path.join(root,'templates')}),
  'set-debug-threshold':(_,name,value,field)=>{savedThreshold={name,value,field};return true;},
  'lab-read-template':(_,name)=>nativeImage.createFromPath(path.join(root,'templates',name)).toDataURL(),
  'lab-save-template':(_,data)=>{if(!data.startsWith('data:image/png;base64,'))throw Error('Not PNG');return 'apply_mercy_heal.png';},
  'lab-save-options':(_,name,o)=>{validateOptions(o);saved=o;return true;},
}))ipcMain.handle(channel,fn);
app.whenReady().then(async()=>{
  session.defaultSession.webRequest.onBeforeRequest({urls:['http://*/*','https://*/*']},(_,cb)=>cb({cancel:true}));
  const win=new BrowserWindow({show:false,width:1120,height:930,webPreferences:{nodeIntegration:true,contextIsolation:false}});
  const errors=[];
  win.webContents.on('console-message',(_,level,message)=>{if(level>=3 && !message.includes('ERR_BLOCKED_BY_CLIENT'))errors.push(message);});
  try{
    for(const page of ['app.html','onboarding.html','debug.html','detection-lab.html']){
      await win.loadFile(path.join(root,'app',page));
      await new Promise(r=>setTimeout(r,400));
      if(page==='app.html'){
        win.webContents.send('menu-pause',true,5);
        await new Promise(r=>setTimeout(r,50));
        await win.webContents.executeJavaScript(`(() => {
          if(!document.getElementById('app-version-title').textContent.endsWith('v${require('../package.json').version}'))throw Error('Incorrect version title');
          if(document.getElementById('menu-pause-status').textContent!=='Paused while in menu')throw Error('Incorrect pause label');
          const image=document.querySelector('img[src="images/friendly-ui-color.png"]');
          if(!image.complete || !image.naturalWidth)throw Error('Friendly UI reference missing');
        })()`);
        await win.webContents.executeJavaScript(`(() => {
          const slider=document.getElementById('max-intensity');
          if(slider.disabled || slider.value!=='100')throw Error('Intensity default not loaded');
          if(!slider.closest('.panel').querySelector('#score-value'))throw Error('Slider outside Score panel');
          slider.value=50;slider.dispatchEvent(new Event('input'));slider.dispatchEvent(new Event('change'));
          if(document.getElementById('max-intensity-value').textContent!=='50%')throw Error('Intensity label not updated');
        })()`);
        await new Promise(r=>setTimeout(r,100));
        if(config.settings.max_intensity!==50)throw Error('Intensity not sent to settings');
        await win.reload();
        await new Promise(r=>setTimeout(r,400));
        await win.webContents.executeJavaScript("if(document.getElementById('max-intensity').value!=='50')throw Error('Saved intensity not restored')");
        fs.writeFileSync(path.join(root,'build/intensity-preview.png'),(await win.webContents.capturePage()).toPNG());
        await win.webContents.executeJavaScript("document.querySelector('[data-nav=\"settings\"]').click()");
        await new Promise(r=>setTimeout(r,100));
        fs.writeFileSync(path.join(root,'build/settings-reference-preview.png'),(await win.webContents.capturePage()).toPNG());
        await win.webContents.executeJavaScript("loadAdvanced().then(()=>{if(!document.getElementById('btn-detection-lab'))throw Error('Missing V2 editor button')})");
      }
      if(page==='debug.html'){
        win.webContents.send('debug-frame',{confidence:{Example:.6},details:{Example:{mode:'masked',threshold:.83}}});
        await new Promise(r=>setTimeout(r,100));
        await win.webContents.executeJavaScript(`(() => {
          const slider=document.getElementById('thr-'+cssId('Example'));
          if(slider.disabled || Number(slider.value)!==.83)throw Error('Slider does not show active masked threshold');
          slider.value=.81;slider.dispatchEvent(new Event('input'));slider.dispatchEvent(new Event('change'));
        })()`);
        await new Promise(r=>setTimeout(r,100));
        if(savedThreshold?.field!=='v2_threshold'||savedThreshold?.value!==.81)throw Error('Wrong threshold saved');
        for (const [score,active] of [[.95,false],[.95,true],[.2,true],[.2,false]]) {
          win.webContents.send('debug-frame',{confidence:{Example:score},
            detections:active?{Example:1}:{},details:{Example:{mode:'masked',threshold:.81}}});
          await new Promise(r=>setTimeout(r,50));
          const state=await win.webContents.executeJavaScript("({active:document.getElementById('card-'+cssId('Example')).classList.contains('matched'),count:document.getElementById('match-count').textContent})");
          if(state.active!==active||state.count!==`${active?1:0} matches`)throw Error('Debug panel did not follow confirmed output');
        }
      }
      if(page==='detection-lab.html'){
        const result=await win.webContents.executeJavaScript(`(async()=>{
          if(canvas.width<2)throw Error('Template did not load');
          const before=ctx.getImageData(0,0,canvas.width,canvas.height).data.filter((_,i)=>i%4===3).reduce((a,b)=>a+b,0);
          const rect=canvas.getBoundingClientRect();paint({clientX:rect.left+rect.width/2,clientY:rect.top+rect.height/2});
          const after=ctx.getImageData(0,0,canvas.width,canvas.height).data.filter((_,i)=>i%4===3).reduce((a,b)=>a+b,0);
          if(after>=before)throw Error('Mask brush did not remove alpha');
          await commitImage();await ipc.invoke('lab-save-options',name,options());return 'mask painted and options saved';
        })()`);
        if(!saved)throw Error('No saved detection options');
        if(saved.confirm_frames!==2||saved.release_ms!==200)throw Error('Editor stabilization defaults differ from engine');
        const screenshot=await win.webContents.capturePage();
        fs.writeFileSync(path.join(root,'build/detection-editor-preview.png'),screenshot.toPNG());
        console.log(result);
      }
      console.log(`${page}: loaded`);
    }
    if(errors.length)throw Error(errors.join('\n'));
    console.log('Offline Electron renderer smoke test passed.');app.exit(0);
  }catch(e){console.error(e.stack);app.exit(1);}
});
