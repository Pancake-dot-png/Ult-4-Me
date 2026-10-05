function installLayout(document) {
  const app=document.querySelector('.app');app.classList.add('refined');
  const labels={main:'Session',triggers:'Tune',advanced:'Advanced',log:'Activity',skins:'Appearance',settings:'Settings'};
  document.querySelectorAll('[data-nav]').forEach(button=>{
    let label=button.querySelector('.nav-label');
    if(!label){button.innerHTML='<span style="display:flex;align-items:center;gap:12px"><span>⚙</span><span class="nav-label"></span></span>';label=button.querySelector('.nav-label');}
    label.textContent=labels[button.dataset.nav];
  });
  const session=document.getElementById('page-main');
  const heading=document.createElement('div');heading.className='ref-session-heading';
  heading.innerHTML='<div><h1>Your session</h1><p>Connect your device, then start watching your game.</p></div>';
  session.prepend(heading);
  const controls=document.getElementById('btn-toggle-vision').parentElement;
  const tools=document.createElement('details');tools.className='ref-secondary';tools.innerHTML='<summary>Session tools</summary><div></div>';controls.append(tools);
  ['btn-reset-score','btn-manual-test','btn-debug-panel'].forEach(id=>tools.lastElementChild.append(document.getElementById(id)));
  document.getElementById('btn-reset-score').className='cta ghost';
  const panic=document.getElementById('btn-mute-toggle');panic.className='cta danger';
  const extras=document.createElement('details');extras.className='ref-secondary';extras.innerHTML='<summary>Configure panic action</summary><div></div>';
  extras.lastElementChild.append(document.getElementById('panic-url').parentElement);panic.closest('.panel-body').append(extras);
  const rail=app.querySelector('.rail');const mark=rail.querySelector('.rail-mark');
  const workspace=document.createElement('div');workspace.className='discord-workspace';workspace.textContent='ULT-4-ME';
  const category=document.createElement('div');category.className='discord-category';category.textContent='Session controls';
  const original=session.querySelector('.two-col');
  const panels=Array.from(original.querySelectorAll('.panel'));
  const homes=panels.map(panel=>({parent:panel.parentElement,margin:panel.style.marginTop}));
  const dashboard=document.createElement('div');dashboard.className='discord-dashboard';
  let discord=false;
  return function setThemeLayout(enabled){
    if(enabled===discord)return;discord=enabled;
    if(enabled){
      mark.remove();rail.prepend(workspace);rail.insertBefore(category,rail.querySelector('.nav'));
      [0,1,3,4,5,2].forEach(index=>{panels[index].classList.add(['dc-score','dc-controls','dc-log','dc-connect','dc-panic','dc-devices'][index]);panels[index].style.marginTop='0';dashboard.append(panels[index]);});
      original.replaceWith(dashboard);
    }else{
      workspace.remove();category.remove();rail.prepend(mark);
      panels.forEach((panel,index)=>{homes[index].parent.append(panel);panel.style.marginTop=homes[index].margin;});dashboard.replaceWith(original);
    }
  };
}
module.exports={installLayout};
