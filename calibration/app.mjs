import {demoFlights,candidates,recommendation,rad} from './model.mjs';
const $=id=>document.getElementById(id);
let config,observer,flights=[],samples=[],step=0,generated=Date.now(),suggestion=null;
let sampleChoices=new Map();
function text(id,value){$(id).textContent=value;}
function radius(){return Number($('radius').value);}
function notice(message){text('save-status',message);}
function validView(){
  for(const id of ['latitude','longitude','airport'])if(!$(id).value.trim()||!$(id).checkValidity())return false;
  return /^[A-Za-z]{3}$/.test($('airport').value);
}
function resetSamples(){samples=[];sampleChoices.clear();updateSuggestion();}
function updateView(){
  if(!validView()){notice('Enter valid coordinates and a three-letter airport code.');return;}
  observer={latitude:Number($('latitude').value),longitude:Number($('longitude').value),airport:$('airport').value.toUpperCase()};
  flights=config?.mode==='mock'?demoFlights(observer,observer.airport,step):[];
  generated=Date.now();resetSamples();notice(config?.mode==='mock'?'Viewpoint updated. Targets are simulated.':'Viewpoint updated locally. Save and restart to change the server search area.');render();
}
function updateSuggestion(){
  suggestion=recommendation(samples);text('recommendation',suggestion.message);
  text('sample-count',`${samples.length} observations in this browser session`);
  $('apply').disabled=suggestion.radius===null;
}
function mark(f,seen){
  const key=`${step}:${f.id}`;
  samples=samples.filter(x=>x.key!==key);samples.push({key,km:f.km,seen});sampleChoices.set(key,seen);
  updateSuggestion();render();
}
function render(){
  if(!observer)return;
  const chosen=candidates(observer,flights,radius(),$('airport-only').checked);
  text('radius-value',`${radius().toFixed(1)} km`);text('count',chosen.length);
  $('flights').replaceChildren();
  for(const f of chosen){
    const row=document.createElement('div');row.className='flight-row';
    const identity=document.createElement('div'),title=document.createElement('div'),route=document.createElement('div');
    title.className='flight-title';title.textContent=f.callsign;
    route.className='flight-route';route.textContent=`${f.origin} → ${f.destination} · ${f.kind}`;identity.append(title,route);
    const direction=document.createElement('div');direction.className='flight-direction';direction.textContent=`${f.km.toFixed(1)} km`;
    const bearing=document.createElement('small');bearing.textContent=`${f.compass} · ${Math.round(f.bearing)}°`;direction.append(bearing);
    const actions=document.createElement('div');actions.className='actions';
    for(const [label,seen] of [['Seen',true],['Not seen',false]]){
      const button=document.createElement('button');button.textContent=label;button.setAttribute('aria-label',`${label}: ${f.callsign}`);
      if(sampleChoices.get(`${step}:${f.id}`)===seen)button.classList.add('selected');
      button.onclick=()=>mark(f,seen);actions.append(button);
    }
    row.append(identity,direction,actions);$('flights').append(row);
  }
  if(!chosen.length){const empty=document.createElement('div');empty.className='empty';empty.textContent=config?.mode==='sandbox'?'No sandbox samples inside this radius. FR24 test positions are fixed and may be far from your location.':'No aircraft in this snapshot inside the selected radius.';$('flights').append(empty);}
  draw(chosen);
}
function draw(chosen){
  const canvas=$('radar'),ctx=canvas.getContext('2d'),cx=320,cy=213,R=174;
  ctx.clearRect(0,0,640,440);ctx.strokeStyle='#2c594c';ctx.lineWidth=1;
  for(const fraction of [.25,.5,.75,1]){ctx.beginPath();ctx.arc(cx,cy,R*fraction,0,Math.PI*2);ctx.stroke();}
  ctx.setLineDash([3,5]);ctx.beginPath();ctx.moveTo(cx-R,cy);ctx.lineTo(cx+R,cy);ctx.moveTo(cx,cy-R);ctx.lineTo(cx,cy+R);ctx.stroke();ctx.setLineDash([]);
  ctx.fillStyle='#7eaa96';ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText('N',cx,25);ctx.fillText('S',cx,405);ctx.fillText('W',cx-R-24,cy+4);ctx.fillText('E',cx+R+24,cy+4);
  ctx.fillStyle='#b4d2a9';ctx.beginPath();ctx.arc(cx,cy,5,0,Math.PI*2);ctx.fill();ctx.font='9px system-ui';ctx.fillText('YOU',cx,cy+22);
  for(const f of chosen){
    const x=cx+Math.sin(rad(f.bearing))*R*f.km/radius(),y=cy-Math.cos(rad(f.bearing))*R*f.km/radius();
    ctx.fillStyle=f.kind==='inbound'?'#dcebac':f.kind==='outbound'?'#f1c285':'#9bbdbc';ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.font='10px system-ui';ctx.fillText(f.callsign,x,y-11);
  }
  ctx.fillStyle='#7eaa96';ctx.textAlign='right';ctx.fillText(`${radius().toFixed(1)} km`,610,26);
}
$('locate').onclick=()=>{
  if(!navigator.geolocation){text('location-status','Geolocation unavailable. Enter coordinates manually.');return;}
  text('location-status','Waiting for browser location permission…');$('locate').disabled=true;
  navigator.geolocation.getCurrentPosition(position=>{
    $('latitude').value=position.coords.latitude.toFixed(6);$('longitude').value=position.coords.longitude.toFixed(6);
    text('location-status',`Estimated accuracy ±${Math.round(position.coords.accuracy)} m. Check your position before saving.`);$('locate').disabled=false;updateView();
  },()=>{text('location-status','Location unavailable or permission denied. Enter coordinates manually.');$('locate').disabled=false;},{enableHighAccuracy:true,timeout:15000,maximumAge:0});
};
$('set-view').onclick=updateView;
$('radius').oninput=render;
$('airport-only').onchange=()=>{resetSamples();render();};
async function refreshSnapshot(){
  $('advance').disabled=true;
  try{
    const response=await fetch('/api/snapshot',{method:'POST',headers:{'Content-Type':'application/json','X-Calibration-Token':config.token},body:'{}'});
    if(!response.ok)throw new Error();
    const snapshot=await response.json();
    step=snapshot.observed_at||step;
    flights=snapshot.flights.map(f=>({...f,callsign:f.callsign||f.id,origin:f.origin||'Unknown',destination:f.destination||'Unknown',kind:f.destination===observer.airport?'inbound':f.origin===observer.airport?'outbound':'nearby'}));
    generated=snapshot.observed_at?Date.parse(snapshot.observed_at):Date.now();
    notice(`${config.mode}: ${snapshot.status}. ${flights.length} returned sample(s). Next eligible poll: ${snapshot.next_poll_at||'unavailable'}.`);
    render();
  }catch{flights=[];render();notice('Snapshot unavailable. Check the local server and selected environment credentials.');}
  finally{$('advance').disabled=false;}
}
$('advance').onclick=()=>{if(!observer)return;if(config.mode!=='mock'){refreshSnapshot();return;}step++;flights=demoFlights(observer,observer.airport,step);generated=Date.now();render();};
$('clear').onclick=()=>{resetSamples();render();};
$('apply').onclick=()=>{if(suggestion?.radius!==null){$('radius').value=suggestion.radius;render();}};
$('confirm-save').onchange=()=>{$('save').disabled=!$('confirm-save').checked||!config;};
$('save').onclick=async()=>{
  if(!validView()){notice('Enter valid coordinates and a three-letter airport code.');return;}
  if(!observer||Number($('latitude').value)!==observer.latitude||Number($('longitude').value)!==observer.longitude||$('airport').value.toUpperCase()!==observer.airport){notice('Click Update viewpoint before saving changed coordinates or airport.');return;}
  $('save').disabled=true;
  try{
    const response=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json','X-Calibration-Token':config.token},body:JSON.stringify({latitude:Number($('latitude').value),longitude:Number($('longitude').value),airport:$('airport').value.toUpperCase(),radius_km:radius(),revision:config.revision})});
    if(!response.ok){notice(response.status===409?'Configuration changed elsewhere. Reload before saving.':'Could not save settings. Check the local helper and try again.');return;}
    const result=await response.json();config.revision=result.revision;
    notice(result.environment_overrides.length?'Saved privately. Process environment overrides are active; remove those overrides and restart the backend to apply.':'Saved privately. Restart the display backend to apply; its previous cached result may remain until the next poll.');
  }catch{notice('Local helper unavailable. Your settings have not been confirmed saved.');}
  finally{$('save').disabled=!$('confirm-save').checked;}
};
setInterval(()=>{const age=Math.floor((Date.now()-generated)/1000);text('sample-age',`${config?.mode||'mock'} snapshot · ${age}s since fetch${age>=300?' · stale, refresh snapshot':''}`);},1000);
try{
  const response=await fetch('/api/config',{cache:'no-store'});if(!response.ok)throw new Error('unavailable');config=await response.json();
  for(const id of ['latitude','longitude','airport'])$(id).value=config[id];
  $('radius').max=Math.max(50,Math.ceil(config.radius_km));text('max-radius',`${$('radius').max} km`);$('radius').value=config.radius_km;
  updateView();
  document.querySelector('.pill').textContent=`● ${config.mode} mode`;
  if(config.mode!=='mock'){
    $('advance').textContent='Refresh snapshot ↗';
    document.querySelector('.notice strong').textContent=config.mode==='sandbox'?'FR24 sandbox — fixed test data':'FR24 production — real aircraft data';
    document.querySelector('.notice span').textContent=config.mode==='sandbox'?'Sandbox ignores location filters and returns static samples. Use it to test connectivity, not sky visibility.':'Requests use your private server credentials and are limited by the schedule, five-minute cache and credit budget.';
    document.querySelector('.sky-footer span').lastChild.textContent=' aircraft in range';
    document.querySelector('.traffic > .hint').textContent='Refresh to request a protected backend snapshot. Radius adjustments only filter the current sample.';
    $('confirm-save').parentElement.lastChild.textContent=' I understand this is a chosen range, not a guarantee of visibility.';
    $('radar').setAttribute('aria-label','North-up aircraft positions around your location');
  }
  notice(`Settings loaded. ${config.mode==='mock'?'Mock samples are active.':'Click Refresh snapshot to test the selected environment.'}`);
}catch{notice('Could not load local settings. Restart the helper and reload.');}
