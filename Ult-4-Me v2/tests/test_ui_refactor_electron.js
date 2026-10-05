// Real Electron renderer with isolated IPC fixtures; never connects to hardware.
const {app,BrowserWindow,ipcMain}=require('electron');
const assert=require('assert/strict');const fs=require('fs');const path=require('path');
const {DEFAULT_SETTINGS,DETECTABLES,REGIONS}=require('../app/src/config');
const fixture={settings:{...DEFAULT_SETTINGS,theme_family:'discord',theme_tint:'dark',lovense_ip:'192.168.1.100'},detectables:DETECTABLES};
const calls=[];let muted=false;let win;
let onboardingDone=false;ipcMain.on('onboarding-done',()=>{onboardingDone=true;});
for(const channel of ['get-config','is-vision-running','start-vision','stop-vision','get-mute-status','get-monitor-count','get-zones','set-config','connect-lovense','disconnect-lovense','get-toys','toggle-mute']){
  ipcMain.handle(channel,(_, ...args)=>{
    calls.push({channel,args});
    if(channel==='get-config')return fixture;
    if(channel==='is-vision-running')return false;
    if(channel==='get-mute-status')return {muted,key:'F8',url:''};
    if(channel==='start-vision')return {ok:false,error:'Renderer test: capture is disabled'};
    if(channel==='get-monitor-count')return 1;
    if(channel==='get-zones')return {regions:REGIONS};
    if(channel==='get-toys')return {};
    if(channel==='connect-lovense')return {ok:true,toys:{}};
    if(channel==='set-config'){fixture.settings[args[0]]=args[1];return true;}
    if(channel==='toggle-mute')return muted=!muted;
    return true;
  });
}
app.setPath('userData',fs.mkdtempSync(path.join(require('os').tmpdir(),'u4m-ui-test-')));
app.whenReady().then(async()=>{
  win=new BrowserWindow({show:false,width:1200,height:800,webPreferences:{nodeIntegration:true,contextIsolation:false,sandbox:false}});
  const errors=[];
  win.webContents.on('console-message',(_,level,message)=>{if(level===3&&!message.includes('net::'))errors.push(message);});
  const appFolder=process.env.U4M_UI_APP_FOLDER||path.join(__dirname,'../app');
  await win.loadFile(path.join(appFolder,'app.html'));
  const run=script=>win.webContents.executeJavaScript(script);
  await run(`new Promise(resolve=>{const poll=()=>document.querySelector('.discord-dashboard')?resolve():setTimeout(poll,25);poll();})`);
  assert.equal(await run(`document.getElementById('ip-full').value`),'192.168.1.100');
  assert.equal(await run(`document.querySelectorAll('#ip-suffix,#ip-prefix,#btn-toggle-ip').length`),0);
  assert.equal(await run(`document.querySelectorAll('.discord-spaces').length`),0);
  for(const [family,tint] of [['plush','cotton'],['cyberpunk','pink'],['discord','light'],['plush','blush'],['discord','dark']]){
    await run(`applyTheme(${JSON.stringify(family)},${JSON.stringify(tint)})`);
    assert.equal(await run(`document.querySelectorAll('#page-main .panel').length`),6);
    assert.equal(await run(`Boolean(document.querySelector('.discord-dashboard'))`),family==='discord');
    if(family==='plush')assert.match(await run(`getComputedStyle(document.getElementById('btn-connect')).backgroundImage`),/linear-gradient/);
  }
  await run(`applyTheme('industrial','trail')`);
  assert.equal(await run(`document.querySelector('.app').classList.contains('discord-light')`),true);
  await run(`applyTheme('industrial','graphite');buildSkinRows()`);
  assert.equal(await run(`document.querySelectorAll('.appearance-variant').length`),10);
  await run(`document.querySelector('.appearance-family:last-child button:last-child').click()`);
  assert.equal(fixture.settings.theme_family,'discord');assert.equal(fixture.settings.theme_tint,'light');
  await run(`document.querySelector('.appearance-family[data-theme="plush"] button:last-child').click();document.querySelector('.appearance-family[data-theme="discord"] button:first-child').click()`);
  assert.equal(fixture.settings.theme_colors.plush,'butter');
  assert.equal(await run(`document.querySelector('.appearance-family[data-theme="plush"] button[aria-pressed="true"]').title`),'Daisy');
  assert.match(await run(`document.querySelector('.appearance-family[data-theme="plush"]').style.background`),/239, 212, 66|#efd442/);
  await win.loadFile(path.join(appFolder,'app.html'));
  await run(`new Promise(resolve=>{const poll=()=>document.querySelector('.discord-dashboard')?resolve():setTimeout(poll,25);poll();})`);
  await run(`buildSkinRows()`);
  assert.equal(await run(`document.querySelector('.appearance-family[data-theme="plush"] button[aria-pressed="true"]').title`),'Daisy');
  await run(`document.getElementById('ip-full').value='';document.getElementById('btn-connect').onclick()`);
  await run(`document.getElementById('ip-full').value='999.2.3.4';document.getElementById('btn-connect').onclick()`);
  assert.equal(calls.filter(call=>call.channel==='connect-lovense').length,0);
  await run(`document.getElementById('ip-full').value='192.168.1.100';document.getElementById('btn-connect').onclick()`);
  assert.deepEqual(calls.find(call=>call.channel==='connect-lovense').args,['192.168.1.100']);
  await run(`document.getElementById('btn-connect').onclick();document.getElementById('btn-mute-toggle').onclick()`);
  assert.equal(await run(`document.getElementById('btn-mute-toggle').textContent`),'Resume output');
  await run(`document.getElementById('btn-mute-toggle').onclick();document.querySelector('[data-nav="settings"]').click()`);
  assert.notEqual(await run(`getComputedStyle(document.getElementById('page-settings')).display`),'none');
  await run(`document.querySelector('[data-nav="main"]').click()`);
  assert.deepEqual(errors,[]);
  // Hidden windows suspend transition timelines; capture stable final styles.
  await run(`const stableStyles=document.createElement('style');stableStyles.textContent='*{transition:none!important}';document.head.append(stableStyles)`);
  const folder=path.join(__dirname,'../build/ui-review');fs.mkdirSync(folder,{recursive:true});
  for(const tint of ['light','dark']){
    await run(`applyTheme('discord','${tint}')`);
    await run(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
    await run(`new Promise(resolve=>setTimeout(resolve,200))`); // Let navigation's 150ms color transition finish.
    assert.equal(await run(`getComputedStyle(document.querySelector('.app')).backgroundColor`),tint==='light'?'rgb(255, 255, 255)':'rgb(49, 51, 56)');
    const navColor=await run(`getComputedStyle(document.querySelector('.nav .is-active')).backgroundColor`);
    assert.equal(navColor,tint==='light'?'rgb(220, 223, 227)':'rgb(64, 66, 73)');
    const screenshot=await win.webContents.capturePage();fs.writeFileSync(path.join(folder,'discord-'+tint+'.png'),screenshot.toPNG());
  }
  win.setSize(960,600);
  await win.loadFile(path.join(appFolder,'onboarding.html'));
  assert.equal(await run(`document.querySelectorAll('input[name="theme"]').length`),3);
  assert.equal(await run(`document.getElementById('ob-continue').disabled`),true);
  for(const [family,count] of [['cyberpunk',4],['plush',4],['discord',2]]){
    await run(`document.querySelector('input[value="${family}"]').click()`);
    assert.equal(await run(`document.querySelectorAll('input[data-family="${family}"]').length`),count);
    assert.equal(await run(`document.querySelector('input[data-family="${family}"]:checked').value`),fixture.settings.theme_colors[family]);
  }
  await run(`document.querySelector('input[value="butter"]').click();document.querySelector('input[name="theme"][value="discord"]').click()`);
  assert.equal(await run(`document.querySelector('input[data-family="plush"]:checked').value`),'butter');
  assert.match(await run(`document.querySelector('.theme-row[data-theme="plush"]').style.background`),/239, 212, 66|#efd442/);
  await run(`document.querySelector('input[value="light"]').click();document.getElementById('ob-gooner-check').click()`);
  assert.equal(await run(`document.getElementById('ob-continue').disabled`),false);
  assert.equal(await run(`document.documentElement.scrollHeight<=innerHeight`),true);
  fs.writeFileSync(path.join(folder,'onboarding.png'),(await win.webContents.capturePage()).toPNG());
  await run(`document.getElementById('ob-continue').onclick()`);
  await new Promise(resolve=>setTimeout(resolve,50));
  assert.equal(onboardingDone,true);assert.equal(fixture.settings.theme_family,'discord');assert.equal(fixture.settings.theme_tint,'light');assert.equal(fixture.settings.onboarding_completed,true);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({status:'passed',rendererErrors:errors,checkedAt:new Date().toISOString()},null,2));
  console.log('Electron renderer passed: startup, legacy theme mapping, theme switches, palette buttons, IP validation/connect/disconnect, mute, settings, and screenshots.');
  win.destroy();app.exit(0);
}).catch(error=>{console.error(error);if(win)win.destroy();app.exit(1);});
