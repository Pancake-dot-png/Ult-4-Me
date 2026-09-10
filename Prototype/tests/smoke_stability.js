const {app,BrowserWindow,ipcMain}=require('electron');
const path=require('path');
const project=path.resolve(__dirname,'../..');
app.setPath('userData',path.join(project,'Prototype/build/stability/smoke-profile'));
ipcMain.handle('get-debug-config',()=>({detectables:{Pulse:{filename:'receive_mercy_heal.png',region:'Receive Heal',points:50,type:0,threshold:.8}},templatesDir:path.join(project,'templates')}));
app.whenReady().then(async()=>{
 const win=new BrowserWindow({show:false,webPreferences:{nodeIntegration:true,contextIsolation:false}});
 try{
  await win.loadFile(path.join(project,'Prototype/electron_test/debug.html'));
  await new Promise(r=>setTimeout(r,250));
  for(const [score,active] of [[.95,false],[.95,true],[.2,true],[.2,false]]){
   win.webContents.send('debug-frame',{confidence:{Pulse:score},detections:active?{Pulse:1}:{}});
   await new Promise(r=>setTimeout(r,30));
   const result=await win.webContents.executeJavaScript("({active:document.getElementById('card-'+cssId('Pulse')).classList.contains('matched'),count:document.getElementById('match-count').textContent})");
   if(result.active!==active || result.count!==`${active?1:0} matches`)throw Error(JSON.stringify(result));
  }
  console.log('Debug panel confirmation/release display passed.');app.exit(0);
 }catch(e){console.error(e);app.exit(1);}
});
