/* Mission Control wall. Renders data/mission.json (live: /api/mission.json; snapshot: inlined). */
(function(){
const TZ='America/New_York', Q=new URLSearchParams(location.search);
const $=s=>document.querySelector(s);
let sceneStart=Date.now(), DATA=null, SNAP=window.__MC_SNAPSHOT__||null, kiosk=Q.get('kiosk')==='1', scene=0, sceneTimer=null;
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function parts(d){const o={};new Intl.DateTimeFormat('en-US',{timeZone:TZ,weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',hour12:true,year:'numeric'}).formatToParts(d).forEach(p=>o[p.type]=p.value);return o}
// "Fri Oct 9 · 3:36 AM ET"  (mirrored exactly in tests/smoke_test.py)
function fmtET(iso){const p=parts(new Date(iso));return `${p.weekday} ${p.month} ${p.day} · ${p.hour}:${p.minute} ${p.dayPeriod} ET`}
function fmtTimeET(iso){const p=parts(new Date(iso));return `${p.hour}:${p.minute} ${p.dayPeriod} ET`}
function fmtFetched(iso){if(!iso)return 'unknown';const p=parts(new Date(iso));return `${p.month} ${p.day}, ${p.hour}:${p.minute} ${p.dayPeriod} ET`}
const FINE=new Set(['SEC','MIN','HR','Second','Minute','Hour']);
function isFine(L){return FINE.has(L.netPrecisionAbbrev)||FINE.has(L.netPrecision)}
// Coarse NETs are shown as the period the source publishes (UTC-based, like LL2), never as a fake time.
function netLabel(L){
  if(!L.net) return 'NET TBD';
  const d=new Date(L.net), y=d.getUTCFullYear(), m=MON[d.getUTCMonth()], a=(L.netPrecisionAbbrev||''), n=(L.netPrecision||'');
  if(isFine(L)) return 'NET '+fmtET(L.net);
  if(/^Day$/i.test(n)||a==='D') return `NET ${m} ${d.getUTCDate()}, ${y} (day only)`;
  if(/^Month$/i.test(n)||a==='M') return `NET ${m} ${y}`;
  let q=a.match(/^Q([1-4])$/); if(q) return `NET Q${q[1]} ${y}`;
  q=a.match(/^H([12])$/); if(q) return `NET H${q[1]} ${y}`;
  if(/^Year$/i.test(n)||a==='Y') return `NET ${y}`;
  return `NET ${n||a} · ${m} ${y}`;
}
function cd(ms){const neg=ms<0;ms=Math.abs(ms);const s=Math.floor(ms/1000),dd=Math.floor(s/86400),hh=Math.floor(s%86400/3600),mm=Math.floor(s%3600/60),ss=s%60;const z=n=>String(n).padStart(2,'0');
  return {neg,html:`${neg?'T+':'T−'}${dd?`${dd}<span class="u">D</span>`:''}${z(hh)}<span class="u">H</span>${z(mm)}<span class="u">M</span>${z(ss)}<span class="u">S</span>`,txt:`${neg?'T+':'T-'}${dd}d ${z(hh)}:${z(mm)}:${z(ss)}`}}
function tminusHTML(L){
  if(!isFine(L)){return `<div class="tminus coarse" data-coarse="1">${esc(netLabel(L).replace(/^NET /,'NET '))}</div>`}
  const c=cd(new Date(L.net)-Date.now());
  return `<div class="tminus" data-tick="${esc(L.net)}">${c.html}</div>`+(c.neg?`<div class="ss-note">T-0 has passed in the saved data — awaiting the next LL2 update.</div>`:'');
}
function statusBadge(L){const a=(L.statusAbbrev||'').toUpperCase();const cls=a==='GO'?'b-go':a==='TBC'?'b-tbc':a==='TBD'?'b-tbd':'b-prec';
  const title={GO:'Go for launch',TBC:'To be confirmed',TBD:'To be determined'}[a]||L.status;return `<span class="badge ${cls}" title="${esc(L.status)}">${esc(a||'?')}</span>`}
function precBadge(L){return `<span class="badge ${isFine(L)?'b-prec':'b-net'}">${isFine(L)?'± '+esc((L.netPrecision||'').toLowerCase()):'NET · '+esc(L.netPrecision||'TBD')}</span>`}
const PADSHORT={'Space Launch Complex 4E':'SLC-4E · Vandenberg','Space Launch Complex 40':'SLC-40 · Cape Canaveral','Launch Complex 39A':'LC-39A · KSC','Orbital Launch Pad 2':'OLP-2 · Starbase','Orbital Launch Pad 1':'OLP-1 · Starbase'};
function padTxt(L){return L.pad==='Unknown Pad'?`Pad TBD · ${L.location}`:`${L.pad} · ${L.location}`}
function windowTxt(L){if(!isFine(L)||!L.windowStart||!L.windowEnd||L.windowStart===L.windowEnd)return isFine(L)?'Instantaneous':'—';return `${fmtTimeET(L.windowStart)} – ${fmtTimeET(L.windowEnd)}`}
function upcoming(){const now=Date.now();return DATA.launches.filter(L=>!(isFine(L)&&new Date(L.net)<now-3*3600e3))}
function srcLine(key,extra){const s=DATA.sources[key]||{};return `<b>SRC</b> <a href="${esc(s.home||s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a> · fetched ${esc(fmtFetched(s.fetchedAt))}${s.origin&&s.origin!=='live'?' · via '+esc(s.origin):''}${s.status&&s.status.startsWith('stale')?' · <span style="color:var(--warn)">'+esc(s.status)+'</span>':''}${extra?' · '+extra:''}`}

function render(){
  const up=upcoming(), H=up[0];
  // hero
  $('#hero').innerHTML=H?`<div class="mname" data-launch-id="${esc(H.id)}" data-mission="${esc(H.mission)}">${esc(H.mission)}</div>
    <div class="veh">${esc(H.vehicle)} · ${esc(H.missionType||'')}${H.orbit?' · '+esc(H.orbit):''}</div>
    ${tminusHTML(H)}
    <dl class="kv"><dt>NET</dt><dd data-net-label>${esc(netLabel(H).replace(/^NET /,''))}</dd>
    <dt>Window</dt><dd>${esc(windowTxt(H))}</dd>
    <dt>Pad</dt><dd data-pad>${esc(padTxt(H))}</dd>
    <dt>Status</dt><dd>${statusBadge(H)}${precBadge(H)}${esc(H.status)}</dd></dl>`:'<div class="ss-note">No upcoming launches in the saved data.</div>';
  $('#hero-status').innerHTML=H?`LL2 updated ${esc(fmtFetched(H.lastUpdated))}`:'';
  $('#queue').innerHTML=up.slice(1,7).map((L,i)=>`<li data-launch-id="${esc(L.id)}" data-idx="${i+1}" data-mission="${esc(L.mission)}" data-net-label="${esc(netLabel(L))}">
     <div class="qm">${statusBadge(L)}${esc(L.mission)}</div><div class="qc">${isFine(L)?`<span data-tick-short="${esc(L.net)}"></span>`:'<span class="badge b-net">NET</span>'}</div>
     <div class="qs">${esc(netLabel(L))} · ${esc(L.vehicle)} · ${esc(L.pad==='Unknown Pad'?'Pad TBD, '+L.location:(PADSHORT[L.pad]||L.pad))}</div></li>`).join('');
  $('#src-launch').innerHTML=srcLine('upcoming',`${DATA.sources.upcoming.count??'?'} upcoming listed · live countdown only at minute/second precision`);

  // last launch (LL2 previous)
  const R0=(DATA.recent||[])[0];
  $('#last').innerHTML=R0?`LAST SPACEX LAUNCH · <b data-last-id="${esc(R0.id)}">${esc(R0.mission)}</b> ${statusBadge(R0)}<br>${esc(R0.vehicle)} · ${esc(fmtET(R0.net))} · <span class="tp" data-tick-short="${esc(R0.net)}"></span><br><span style="color:var(--faint)">SRC LL2 · fetched ${esc(fmtFetched((DATA.sources.previous||{}).fetchedAt))}${(DATA.sources.previous||{}).origin&&(DATA.sources.previous||{}).origin!=='live'?' (via boyd-wall cache)':''}</span>`:'';
  $('#last').title=$('#last').innerText.replace(/\s*\n\s*/g,' · ');  // QA 2026-10-07: header lines may truncate; full text on hover
  // globe pads
  const pads=DATA.pads.map(p=>Object.assign({},p,{short:PADSHORT[p.name]||p.name}));
  pads.forEach(p=>{if(/pad TBD/.test(p.name)||p.name==='Orbital Launch Pad 1')p.label=false;if(p.name==='Launch Complex 39A'){p.dy=-22}if(p.name==='Space Launch Complex 40'){p.dy=14}if(p.name==='Space Launch Complex 4E'){p.dx=-10}if(p.name==='Orbital Launch Pad 2'){p.dx=-10;p.dy=16}});
  MCGlobe.setPads(pads);
  $('#globe-caption').textContent='day/night from sun · pads LL2 · shells illustrative';
  $('#globe-legend').innerHTML=`<div><i style="background:#ff8a3d"></i>pad with an upcoming SpaceX launch (LL2 coordinates)</div><div><i style="background:#9baac8"></i>recent Starship pad</div><div><i style="background:#5cc8ff"></i>illustrative Starlink shells · 53° 43° 70° 97° (dots not to scale · not tracking)</div><div><i style="background:#0a1430;border:1px solid #345"></i>night side · terminator from the sun\'s position now</div>`;
  $('#src-globe').innerHTML=srcLine('upcoming','pad lat/lon from LL2 · coastline: Natural Earth 1:110m');

  // starlink
  const S=DATA.starlink, T=S&&S.total;
  if(T){const fmt=n=>n==null?'—':n.toLocaleString('en-US');
    const gens=Object.entries(S.byGen).filter(([k,v])=>v.launched);
    const mx=Math.max(...gens.map(([k,v])=>v.inOrbit||0),1);
    $('#starlink').innerHTML=`<div class="sl-hero"><span class="sl-big" data-k="inOrbit" data-v="${T.inOrbit}">${fmt(T.inOrbit)}</span><span class="sl-lbl">Starlink satellites in orbit</span></div>
      <div class="sl-grid">
       <div class="stat"><div class="v" data-k="working" data-v="${T.working}">${fmt(T.working)}</div><div class="k">working</div></div>
       <div class="stat"><div class="v" data-k="operational" data-v="${T.operational}">${fmt(T.operational)}</div><div class="k">in operational orbit</div></div>
       <div class="stat"><div class="v" data-k="launched" data-v="${T.launched}">${fmt(T.launched)}</div><div class="k">launched, all time</div></div>
       <div class="stat"><div class="v" data-k="ascent" data-v="${T.ascent}">${fmt(T.ascent)}</div><div class="k">still raising orbit</div></div>
       <div class="stat"><div class="v" data-k="drift" data-v="${T.drift}">${fmt(T.drift)}</div><div class="k">drifting to plane</div></div>
       <div class="stat"><div class="v" data-k="down" data-v="${T.down}">${fmt(T.down)}</div><div class="k">reentered / down</div></div>
      </div>
      <div class="gens">${gens.map(([k,v])=>`<div class="gen"><span>${esc(k.replace('Starlink ',''))}</span><div class="bar"><span style="width:${(v.inOrbit/mx*100).toFixed(1)}%"></span></div><span class="n" data-gen="${esc(k)}" data-v="${v.inOrbit}">${fmt(v.inOrbit)}</span></div>`).join('')}</div>`;
    $('#sl-asof').textContent='as of '+S.dataAsOf;
  } else $('#starlink').innerHTML='<div class="ss-note">Starlink statistics unavailable.</div>';
  $('#src-starlink').innerHTML=srcLine('starlink',`table data as of <b>${esc(S&&S.dataAsOf||'?')}</b> · bars = in orbit by generation`);

  // starship status
  const SS=DATA.starship, F=SS.upcoming[0];
  const j15=(DATA.journal||[]).find(j=>/Flight 15/i.test(j.title));
  $('#ss-status').innerHTML=(F?`<div class="ss-next" data-ss-next="${esc(F.label)}"><div class="t">${esc(F.label)} ${statusBadge(F)}</div>
      <div>${esc(netLabel(F))} · ${esc(PADSHORT[F.pad]||F.pad)}</div>
      ${isFine(F)?`<div class="tminus" style="font-size:calc(var(--u)*1.6)" data-tick="${esc(F.net)}"></div>`:'<div class="ss-note">No official date in LL2 — shown as the source publishes it.</div>'}
      ${j15?`<div class="ss-note">Jim (${esc(j15.date)}): ${esc(j15.text.slice(0,95)+'…')} ${j15.links.map(l=>`<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join(' · ')}</div>`:''}</div>`:'<div class="ss-note">No upcoming Starship flight in LL2.</div>')+`<div class="src" id="src-ssstatus" style="margin-top:0">${srcLine('starship')}</div>`
    +(SS.updates&&SS.updates[0]&&(new Date(DATA.generatedAt)-new Date(SS.updates[0].date))<90*864e5?`<div class="ss-note"><b style="color:var(--dim)">Latest LL2 Starship update · ${esc(fmtFetched(SS.updates[0].date))} ${new Date(SS.updates[0].date).getFullYear()}:</b> ${esc(SS.updates[0].text)} ${SS.updates[0].url?`<a href="${esc(SS.updates[0].url)}" target="_blank" rel="noopener">source</a>`:''}</div>`:'');

  // timeline
  const fl=SS.flights, integ=fl.filter(f=>f.integrated), proto=fl.filter(f=>!f.integrated);
  const oc=s=>/Partial/i.test(s)?'c-warn':/Fail/i.test(s)?'c-bad':/Success/i.test(s)?'c-ok':'c-up';
  const short=s=>/Partial/i.test(s)?'PARTIAL':/Fail/i.test(s)?'FAILURE':/Success/i.test(s)?'SUCCESS':(s||'').toUpperCase();
  const nodes=[...integ,...SS.upcoming.slice(0,1).map(f=>Object.assign({},f,{up:true}))];
  const x0=14.5, x1=97.5, step=(x1-x0)/Math.max(1,nodes.length-1);
  const dshort=iso=>{const d=new Date(iso);return `${MON[d.getUTCMonth()]} ${d.getUTCDate()} ’${String(d.getUTCFullYear()).slice(2)}`};
  let h=`<div class="track"></div>`;
  proto.forEach((f,i)=>{h+=`<div class="node small ${oc(f.status)}" style="left:${(0.6+i*(8.4/Math.max(1,proto.length-1))).toFixed(2)}%" data-label="${esc(f.label)}" data-status="${esc(f.status)}" title="${esc(f.label+' · '+f.status)}"><div class="o"></div></div>`});
  h+=`<div class="proto" style="left:0">${proto.length} prototype hops 2019–21<br>${proto.filter(f=>/Success/.test(f.status)).length} ok · ${proto.filter(f=>/Partial/.test(f.status)).length} partial · ${proto.filter(f=>/Fail/.test(f.status)&&!/Partial/.test(f.status)).length} fail</div>`;
  nodes.forEach((f,i)=>{const c=f.up?'c-up':oc(f.status);h+=`<div class="node ${c} ${f.up?'up':''}" style="left:${(x0+i*step).toFixed(2)}%" data-label="${esc(f.label)}" data-status="${esc(f.status)}" data-net="${esc(f.net)}" title="${esc(f.mission+(f.failreason?' — '+f.failreason:''))}">
     <div class="r">${f.up?esc(netLabel(f).replace(/^NET /,'NET ')):short(f.status)}</div><div class="o"></div><div class="l">${esc(f.label)}</div><div class="d">${f.up?esc((f.statusAbbrev||'')):dshort(f.net)}</div></div>`});
  $('#timeline').innerHTML=h;
  const out=SS.integratedOutcomes||{}, cnt=k=>Object.entries(out).filter(([s])=>k(s)).reduce((a,[,n])=>a+n,0);
  $('#ss-record').innerHTML=`<span data-integrated="${SS.integratedCount}">${SS.integratedCount} integrated flights</span> · <span class="c-ok">${cnt(s=>/Success/.test(s))} success</span> · <span class="c-warn">${cnt(s=>/Partial/.test(s))} partial</span> · <span class="c-bad">${cnt(s=>/Fail/.test(s)&&!/Partial/.test(s))} failure</span> <span style="color:var(--faint)">(LL2 outcome labels)</span>`;
  $('#src-starship').innerHTML=srcLine('starship','outcome = LL2 launch status; dates UTC');

  // journal
  const J=DATA.journal||[];
  const card=j=>`<div class="jc" data-journal-title="${esc(j.title)}"><div class="jd">${esc(j.date)} · ${esc(j.section||'')}</div><div class="jt">${esc(j.title)}</div><div class="jx">${esc((j.text||'').slice(0,110))}${(j.text||'').length>110?'…':''}</div><div class="jl">${j.links.map(l=>`<a href="${esc(l.url)}" target="_blank" rel="noopener">↗ ${esc(l.label)}</a>`).join('')}</div></div>`;
  $('#journal-track').innerHTML=J.map(card).join('')+J.map(card).join('');
  document.documentElement.style.setProperty('--marq',Math.max(60,J.length*9)+'s');
  const js=DATA.sources.journal||{};
  $('#journal-files').textContent=`${J.length} SpaceX/Starlink items · ${ (js.files||[]).join(', ')}`;

  $('#foot-l').textContent=`Data generated ${fmtFetched(DATA.generatedAt)} · LL2 / The Space Devs · J. McDowell (planet4589.org) · Jim's journal · dates shown exactly as published (NET/TBD kept)`;
  if(SNAP){$('#mode-pill').textContent='OFFLINE SNAPSHOT · saved '+fmtFetched(SNAP.savedAt);$('#mode-pill').classList.add('snap')}
  tick(); applyScene(); fitQueue();
}
function fitQueue(){const q=$('#queue');if(!q)return;const b=q.getBoundingClientRect().bottom;q.querySelectorAll('li').forEach(li=>{li.style.display=''});q.querySelectorAll('li').forEach(li=>{if(li.getBoundingClientRect().bottom>b+1)li.style.display='none'})}
window.addEventListener('resize',()=>DATA&&fitQueue());

function tick(){
  const now=new Date(),p=parts(now);
  $('#clock-et').textContent=`${p.hour.padStart(2,'0')}:${p.minute}:${p.second} ${p.dayPeriod}`;
  $('#clock-utc').textContent=now.toISOString().slice(11,19);
  $('#clock-date').textContent=`${p.weekday} ${p.month} ${p.day}, ${p.year}`;
  document.querySelectorAll('[data-tick]').forEach(el=>{const c=cd(new Date(el.dataset.tick)-now);el.innerHTML=c.html});
  document.querySelectorAll('[data-tick-short]').forEach(el=>{const c=cd(new Date(el.dataset.tickShort)-now);el.textContent=c.txt});
}

// ---------------- kiosk scenes
const SCENES=['overview','launch0','launch1','launch2','starship','starlink','journal'];
function applyScene(){
  if(!DATA) return; const sc=SCENES[scene]; const spot=$('#spot');
  document.body.className='scene-'+sc+(sc==='overview'?'':' focusing')+(kiosk?' kiosk':'');
  sceneStart=Date.now(); const kl=$('#kbar-label'); if(kl) kl.textContent=`SCENE ${scene+1}/${SCENES.length} · ${sc.replace(/launch(\d)/,(m,i)=>'LAUNCH '+(+i+1)).toUpperCase()}`;
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('focus'));
  document.querySelectorAll('#queue li').forEach(li=>li.classList.remove('hl'));
  spot.classList.remove('show','at-top');
  const up=upcoming();
  if(sc.startsWith('launch')){
    const i=+sc.slice(6), L=up[i]; if(!L){MCGlobe.focus(null);return}
    $('#p-globe').classList.add('focus');$('#p-launch').classList.add('focus');
    const li=document.querySelector(`#queue li[data-idx="${i}"]`); if(li) li.classList.add('hl');
    const pad=DATA.pads.find(p=>p.name===L.pad)||{lat:L.lat,lon:L.lon,name:L.pad}; MCGlobe.focus(pad);
    spot.innerHTML=`<div class="card"><div class="k">${i===0?'NEXT SPACEX LAUNCH':'LAUNCH '+(i+1)+' IN QUEUE'}</div><div class="m">${esc(L.mission)}</div>${tminusHTML(L)}
      <div class="s">${statusBadge(L)} ${esc(netLabel(L))}</div><div class="s">${esc(L.vehicle)} · ${esc(padTxt(L))}</div>
      <div class="s2">${srcLine('upcoming')}</div></div>`;
    spot.classList.add('show'); tick();
  } else {
    MCGlobe.focus(null);
    const map={starship:'#p-starship',starlink:'#p-right',journal:'#p-journal'}; if(map[sc]) $(map[sc]).classList.add('focus');
    if(sc==='starship'){const fl=DATA.starship.flights.filter(f=>f.integrated),Lf=fl[fl.length-1],N=DATA.starship.upcoming[0];
      if(Lf){spot.innerHTML=`<div class="card top"><div class="k">STARSHIP · LATEST INTEGRATED FLIGHT</div><div class="m">${esc(Lf.label)} · ${esc(Lf.mission.replace(/\s*\(Starship Flight \d+\)/,""))}</div>
        <div class="s">${esc(fmtET(Lf.net))} · ${esc(Lf.status)} · ${esc(PADSHORT[Lf.pad]||Lf.pad)}</div>
        ${N?`<div class="s">Next: <b>${esc(N.label)}</b> ${statusBadge(N)} ${esc(netLabel(N))}</div>`:''}
        <div class="s2">${srcLine('starship')}</div></div>`;spot.classList.add('show','at-top')}}
    if(sc==='starlink'){const T=(DATA.starlink&&DATA.starlink.total)||{};
      spot.innerHTML=`<div class="card"><div class="k">STARLINK CONSTELLATION</div><div class="m">${(T.inOrbit||0).toLocaleString('en-US')} in orbit</div>
        <div class="s">${(T.working||0).toLocaleString('en-US')} working · ${(T.operational||0).toLocaleString('en-US')} operational orbit · ${(T.launched||0).toLocaleString('en-US')} launched all-time</div>
        <div class="s">as of ${esc((DATA.starlink&&DATA.starlink.dataAsOf)||'?')}</div>
        <div class="s2">${srcLine('starlink')}</div></div>`;spot.classList.add('show')}
    if(sc==='journal'){const J=(DATA.journal||[])[0];
      if(J){spot.innerHTML=`<div class="card"><div class="k">FROM JIM'S JOURNAL</div><div class="m">${esc(J.title)}</div>
        <div class="s">${esc(J.date)} · ${esc(J.section||'')}</div>
        <div class="s">${esc((J.text||'').slice(0,140))}${(J.text||'').length>140?'…':''}</div>
        <div class="s2">${(J.links||[]).map(l=>esc(l.label)).join(' · ')} · ${(DATA.journal||[]).length} SpaceX/Starlink cards</div></div>`;spot.classList.add('show')}}
  }
}
function dwell(){return +(Q.get('dwell')||10)*1000}
setInterval(()=>{const f=$('#kbar-fill');if(f&&kiosk)f.style.width=Math.min(100,(Date.now()-sceneStart)/dwell()*100)+'%'},100);
function setKiosk(on){kiosk=on;document.body.classList.toggle('kiosk',on);$('#kiosk-pill').textContent=on?'KIOSK · AUTO-CYCLE':'KIOSK OFF';$('#kiosk-pill').classList.toggle('on',on);clearInterval(sceneTimer);
  if(on) sceneTimer=setInterval(()=>{scene=(scene+1)%SCENES.length;applyScene()},dwell()); else {scene=0;applyScene()}}
document.addEventListener('keydown',e=>{if(e.key==='k'||e.key==='K')setKiosk(!kiosk);else if(/^[1-7]$/.test(e.key)){scene=+e.key-1;applyScene()}else if(e.key==='r'||e.key==='R')load()});
$('#kiosk-pill').addEventListener('click',()=>setKiosk(!kiosk));

async function load(){
  if(SNAP){DATA=SNAP.data;render();return}
  try{const r=await fetch('/api/mission.json?ts='+Date.now());DATA=await r.json();render()}catch(e){console.error(e)}
}
if(Q.get('still')==='1'){MCGlobe.still=true;MCGlobe.setView(-95,26);document.documentElement.style.setProperty('--marq','100000s')}
load().then(()=>{if(Q.get('scene')){scene=Math.max(0,SCENES.indexOf(Q.get('scene')));applyScene()}if(kiosk)setKiosk(true)});
setInterval(tick,1000);
if(!SNAP) setInterval(load,60000);
})();
