const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
function walk(dir) {
  for (const entry of fs.readdirSync(dir,{withFileTypes:true})) {
    const file=path.join(dir,entry.name);
    if(entry.isDirectory()) walk(file);
    else if(file.endsWith('.js')) new vm.Script(fs.readFileSync(file,'utf8'),{filename:file});
    else if(file.endsWith('.html')) {
      const html=fs.readFileSync(file,'utf8');
      for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
        if(match[1].trim()) new vm.Script(match[1],{filename:file});
      }
    }
  }
}
walk(path.join(__dirname,'../app'));
const {validateOptions}=require('../app/src/detection-options');
const valid={filename:'example.png',examples:[],match_mode:'auto',v2_threshold:.9,scale_tolerance:0,confirm_frames:1,release_ms:0,edge_tolerance:2};
validateOptions(valid);
for(const bad of [{...valid,filename:'../escape.png'},{...valid,examples:Array(6).fill('a.png')},{...valid,confirm_frames:1.2},{...valid,scale_tolerance:50}]) assert.throws(()=>validateOptions(bad));
console.log('UI scripts parse; detection options reject invalid inputs.');
const {getThreshold}=require('../app/src/debug-threshold');
const det={threshold:.65,v2_threshold:.76};
assert.deepEqual(getThreshold(det,{mode:'masked',threshold:.76}),{mode:'masked',field:'v2_threshold',value:.76});
assert.equal(getThreshold(det,{mode:'legacy',threshold:.65}).field,'threshold');
assert.equal(getThreshold(det).field,null);
assert.equal(getThreshold(det,{mode:'masked',threshold:.76},{value:.82}).value,.82);
console.log('Debug threshold follows the active matcher and pending edits.');
