(function(){
"use strict";
var D = JSON.parse(document.getElementById("data").textContent);
var MAN = ["jan","feb","mar","apr","maj","jun","jul","aug","sep","okt","nov","dec"];
var STAT = [["utkast","Utkast"],["skickad","Skickad"],["intervju","Intervju"],["erbjudande","Erbjudande"],["nej","Nej"]];
var IKON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="5" y="5" width="8.5" height="8.5" rx="2"/><path d="M3 10.5V3.8C3 3.4 3.4 3 3.8 3h6.7"/></svg>';
function $(id){return document.getElementById(id);}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function dagar(d){if(!d)return null;return Math.round((new Date(d+"T00:00:00")-new Date(D.idag+"T00:00:00"))/864e5);}
function kort(d){if(!d)return "";var p=d.split("-");return (+p[2])+" "+MAN[+p[1]-1];}
function kopiera(text){return '<button type="button" class="btn" data-kopiera="'+esc(text)+'" aria-label="Kopiera till Claude: '+esc(text)+'">'+IKON+'Kopiera till Claude</button>';}
function tom(rub,rad,fras,knapp){return '<div class="tom"><h3>'+esc(rub)+'</h3><p>'+esc(rad)+'</p>'+(fras?'<button type="button" class="btn prim" data-kopiera="'+esc(fras)+'">'+IKON+esc(knapp||"Kopiera till Claude")+'</button>':'')+'</div>';}

/* huvud */
var d0=new Date(D.idag+"T00:00:00");
$("datum").textContent=["söndag","måndag","tisdag","onsdag","torsdag","fredag","lördag"][d0.getDay()]+" "+kort(D.idag);
var fn=(D.profil.namn||"").split(" ")[0];
$("halsning").textContent=fn?"Hej "+fn:"Ditt jobbsökande";
$("genererad").textContent="Uppdaterad "+D.genererad;

/* resa */
var nu=null;
D.resa.forEach(function(s){if(!nu&&s.status!=="klar")nu=s.id;});
$("resa").innerHTML=D.resa.map(function(s){
  var st={klar:"klart",pagar:"pågår",ej:"inte påbörjat"}[s.status];
  return '<li class="'+s.status+(s.id===nu?" nu":"")+'"'+(s.id===nu?' aria-current="step"':'')+'><span class="sn">'+esc(s.namn)+'</span><span class="sr2">'+esc(s.rad)+'</span><span class="sr">, '+st+'</span></li>';
}).join("");
$("nasta").innerHTML='<div><div class="lbl">Nästa steg</div><p class="fras">”'+esc(D.nasta.fras)+'”</p></div>'+
  '<button type="button" class="btn prim" data-kopiera="'+esc(D.nasta.fras)+'">'+IKON+'Kopiera till Claude</button>';

/* profil */
var P=D.profil, grupper=[];
function grupp(rub,lista,acc){if(!lista||!lista.length)return;grupper.push('<div class="chipgrupp"><h3>'+rub+'</h3><ul class="chips">'+lista.map(function(x,i){return '<li class="chip'+(acc?" a":"")+'">'+(acc?"<b>"+(i+1)+"</b>":"")+esc(x)+'</li>';}).join("")+'</ul></div>');}
grupp("Riktning",P.riktningar.concat(P.orter));
grupp("Det viktigaste",P.varden,true);
grupp("Gränser",P.granser);
$("profil").innerHTML=grupper.length?'<div class="chiprad">'+grupper.join("")+'</div>':
  '<p class="sub" style="margin:0">Fylls i när du och Claude pratat om vad du vill. <button type="button" class="btn" data-kopiera="Hjälp mig ta reda på vad jag vill jobba med." style="margin-left:6px">'+IKON+'Börja</button></p>';


/* riktningar (rollkort) */
(function(){
  var R=D.riktningar||{kort:[]};
  if(!R.kort.length)return;
  $("riktningar").hidden=false;
  $("rikt-vikter").textContent=R.vikter_egna?"Dina vikter":"Standardvikter · be Claude ändra dem";
  function pct(x){return x==null?"–":Math.round(x*100)+" %";}
  function chip(c,skav){return '<li class="cit'+(skav?" skav":"")+'" title="'+esc(c.text)+'">”'+esc(c.citat)+'”<small>'+esc(c.fas)+'</small></li>';}
  function lista(rub,l){return l&&l.length?'<h4>'+rub+'</h4><ul>'+l.join("")+'</ul>':"";}
  $("riktlista").innerHTML=R.kort.map(function(k){
    var p=k.total==null?0:k.total, rad=[];
    if(k.volym)rad.push('<b>'+(k.volym.ar||0)+'</b> annonser/år · '+esc(k.volym.trend)+(k.volym.procent!=null?' ('+(k.volym.procent>0?"+":"")+k.volym.procent+' %)':''));
    else if(k.typ==="stanna")rad.push(esc(k.roll||"Ditt nuvarande jobb")+" idag");
    if(k.glapp)rad.push((k.glapp.harda_saknas.length?'<b class="varn">Hårt krav saknas</b> · ':'')+'Vanligt efterfrågat: du har <b>'+k.glapp.onsk_har+'</b> av '+k.glapp.onsk_av);
    var det=
      lista("Arbetsuppgifter",k.uppgifter.map(function(u){return '<li>'+esc(u.text)+(u.andel!=null?' <small>'+pct(u.andel)+'</small>':'')+'</li>';}))+
      (k.crafting?lista("Det du kan ändra",k.crafting.map(function(x){return '<li>'+esc(x)+'</li>';})):"")+
      (k.tisdag?'<h4>En vanlig tisdag</h4><p>'+esc(k.tisdag)+'</p>':'')+
      lista("Passar för att",k.passar.map(function(c){return '<li>'+esc(c.text)+' <small>”'+esc(c.citat)+'” · '+esc(c.fas)+'</small></li>';}))+
      lista("Skaver",k.skav.map(function(c){return '<li>'+esc(c.text)+' <small>”'+esc(c.citat)+'” · '+esc(c.fas)+'</small></li>';}).concat(
        k.glapp?k.glapp.harda_saknas.map(function(x){return '<li><b>Hårt krav som saknas:</b> '+esc(x)+'</li>';}):[]))+
      (k.glapp&&k.glapp.saknas.length?'<h4>Önskelista du inte har (går ofta ändå)</h4><ul>'+k.glapp.saknas.map(function(x){return '<li>'+esc(x)+'</li>';}).join("")+'</ul>':'')+
      (k.arbetsgivare.length?'<h4>Anställer i regionen</h4><p>'+k.arbetsgivare.map(esc).join(" · ")+'</p>':'')+
      (k.lon?'<h4>Lön</h4><p>'+esc(k.lon)+'</p>':'')+
      lista("Aktuella annonser",k.annonser.map(function(a){return '<li><a href="'+esc(a.url)+'" target="_blank" rel="noopener">'+esc(a.rubrik)+'</a> <small>'+esc(a.bolag)+'</small></li>';}))+
      '<h4>Matrisen</h4><p class="sub">Sorteringsvärde '+(k.total==null?"–":k.total)+' (täckning '+pct(k.tackning)+'). En karta, inte ett betyg.</p><table class="dims">'+k.dims.map(function(d){return '<tr><th>'+esc(d.namn)+'</th><td>'+esc(d.visa)+'</td></tr>';}).join("")+'</table>';
    return '<article class="card rk'+(k.typ==="stanna"?" stanna":"")+'">'+
      '<div class="rkhuvud"><h3>'+esc(k.titel)+'</h3></div>'+
      (k.etikett?'<span class="etikett e-'+etiklass(k.etikett)+'">'+esc(k.etikett)+'</span>':'')+
      (k.motivering?'<p class="motiv">'+esc(k.motivering)+'</p>':'')+
      ((k.passar.length||k.skav.length)?'<ul class="cits">'+k.passar.slice(0,k.skav.length?1:2).map(function(c){return chip(c);}).join("")+(k.skav[0]?chip(k.skav[0],true):"")+'</ul>':'<p class="sub">Inga citat än</p>')+
      '<p class="rkrad">'+rad.join('<span aria-hidden="true"> · </span>')+'</p>'+
      '<details class="mer"><summary>Detaljer</summary><div class="rkdet">'+det+'</div></details></article>';
  }).join("");
})();

/* jobb */
var filter="alla", q="";
var nJ=D.jobb.length;
$("n-jobb").textContent=nJ||"";
function etiklass(e){e=e||"";return /^Bryter/.test(e)?"brott":/^Möjlig/.test(e)?"mojlig":/^Stark/.test(e)?"stark":/^Sträck/.test(e)?"strack":/^Bra/.test(e)?"bra":"svag";}
function jobbkort(j){
  var dl=dagar(j.deadline), t=[], fl=[];
  if(j.joker)t.push('<span class="tag joker">Joker</span>');
  if(j.strackjobb&&!/^Sträck/.test(j.etikett))t.push('<span class="tag strack" title="'+esc(j.strackjobb)+'">Sträckjobb</span>');
  if(j.status==="intressant")t.push('<span class="tag">Sparad</span>');
  if(dl!=null&&dl>=0)t.push('<span class="tag'+(dl<=7?" snart":"")+'">'+(dl===0?"Sista dag idag":dl<=7?dl+" dagar kvar":"Senast "+kort(j.deadline))+'</span>');
  if(j.distans===2)t.push('<span class="tag">Distans</span>');else if(j.distans===1)t.push('<span class="tag">Delvis distans</span>');
  if(j.arbetsgivarkort){var a=j.arbetsgivarkort;t.push('<button type="button" class="tag ak" data-kopiera="Hur är det att jobba på '+esc(a.namn)+'? Berätta om arbetsgivarkortet." title="'+a.stammer+' stämmer, '+a.skaver+' skaver'+(a.varningar?', '+a.varningar+' varningssignaler':'')+'">Arbetsgivarkort'+(a.varningar?' · '+a.varningar+' att kolla':'')+'</button>');}
  (j.granbrott||[]).forEach(function(b){fl.push('<li class="brott">Bryter mot din gräns: '+esc(b)+'</li>');});
  (j.hart_krav||[]).forEach(function(k){fl.push('<li>Hårt krav att kolla: '+esc(k)+'</li>');});
  (j.flaggor||[]).forEach(function(f){fl.push('<li>'+esc(f[0].toUpperCase()+f.slice(1))+'</li>');});
  var fras="Gör en ansökan till jobb "+j.uid+" ("+j.titel+(j.bolag?", "+j.bolag:"")+")";
  var et=j.etikett||(j.joker?"Joker – värd en titt":"Ej bedömd");
  if(/^Bryter/.test(et)&&fl.length)et="Bryter mot din gräns"+((j.granbrott||[]).length>1?" ("+j.granbrott.length+")":"")+" – du avgör";
  return '<article class="card jobb"><div><span class="etikett e-'+etiklass(et)+'">'+esc(et)+'</span>'+
    '<h3>'+(j.url?'<a href="'+esc(j.url)+'" target="_blank" rel="noopener">'+esc(j.titel)+'</a>':esc(j.titel))+'</h3>'+
    '<div class="sub">'+esc([j.bolag,j.ort].filter(Boolean).join(" · "))+'</div></div>'+
    (j.motivering?'<p class="motiv">'+esc(j.motivering)+'</p>':'')+
    (fl.length?'<ul class="flaggor">'+fl.join("")+'</ul>':'')+
    (t.length?'<div class="taggar">'+t.join("")+'</div>':'')+
    (j.utdrag?'<details class="mer"><summary>Ur annonsen</summary><p>'+esc(j.utdrag)+'</p></details>':'')+
    '<div class="fot2">'+kopiera(fras)+'</div></article>';
}
function ritaJobb(){
  var p=$("p-jobb");
  if(!nJ){p.innerHTML=tom("Inga jobb än","När vi letat dyker de bästa träffarna upp här.","Leta nya jobb åt mig.","Kopiera: Leta nya jobb");return;}
  var l=D.jobb.filter(function(j){
    if(filter==="nya"&&j.status!=="ny")return false;
    if(filter==="sparade"&&j.status!=="intressant")return false;
    if(filter==="jokrar"&&!j.joker)return false;
    if(q){var h=(j.titel+" "+j.bolag+" "+j.ort+" "+j.motivering).toLowerCase();if(h.indexOf(q)<0)return false;}
    return true;});
  if(!p.firstChild||!p.querySelector(".verktyg")){
    p.innerHTML='<div class="verktyg"><label class="sr" for="sok">Sök bland jobben</label><input id="sok" class="sok" type="search" placeholder="Sök titel, bolag, ort">'+
      '<div class="seg" role="group" aria-label="Visa">'+[["alla","Alla"],["nya","Nya"],["sparade","Sparade"],["jokrar","Jokrar"]].map(function(f){return '<button type="button" data-filter="'+f[0]+'" aria-pressed="'+(f[0]===filter)+'">'+f[1]+'</button>';}).join("")+'</div></div><div class="grid" id="jobblista"></div>';
    $("sok").addEventListener("input",function(e){q=e.target.value.trim().toLowerCase();ritaJobb();});
  }
  p.querySelectorAll("[data-filter]").forEach(function(b){b.setAttribute("aria-pressed",b.dataset.filter===filter);});
  $("jobblista").innerHTML=l.length?l.map(jobbkort).join(""):'<p class="sub">Inget matchar.</p>';
}
document.addEventListener("click",function(e){var b=e.target.closest("[data-filter]");if(b){filter=b.dataset.filter;ritaJobb();}});
ritaJobb();

/* ansökningar */
var A=D.ansokningar, forf={};D.forfallna.forEach(function(m){forf[m]=1;});
$("n-ans").textContent=A.length||"";
(function(){
  var p=$("p-ans");
  if(!A.length){p.innerHTML=tom("Inga ansökningar än","Välj ett jobb under Jobb och kopiera frasen till Claude.");return;}
  p.innerHTML=(D.forfallna.length?'<p class="verktyg"><span class="tag snart">'+D.forfallna.length+' att följa upp</span><button type="button" class="btn" data-kopiera="Hjälp mig följa upp mina ansökningar.">'+IKON+'Följ upp med Claude</button></p>':'')+
  '<div class="tavla">'+STAT.map(function(s){
    var l=A.filter(function(a){return a.status===s[0];});
    return '<section class="kol" aria-label="'+s[1]+'"><h3>'+s[1]+'<span>'+l.length+'</span></h3>'+(l.length?l.map(function(a){
      var info=[];
      if(a.status==="utkast"&&a.deadline)info.push("Senast "+kort(a.deadline));
      if(a.skickad)info.push("Skickad "+kort(a.skickad));
      if(a.foljupp&&(a.status==="skickad"||a.status==="intervju"))info.push((forf[a.mapp]?"Följ upp nu":"Följ upp "+kort(a.foljupp)));
      var iv=a.intervju;
      if(iv&&iv.datum)info.push("Intervju "+kort(iv.datum)+(iv.tid?" "+iv.tid:"")+(iv.format?" ("+iv.format+")":""));
      if(iv&&iv.fragor)info.push(iv.klara+" av "+iv.fragor+" svar förberedda");
      var lank=Object.keys(a.filer).filter(function(n){return /pdf$/.test(n);}).map(function(n){return '<a href="'+encodeURI(a.filer[n])+'">'+(n==="cv.pdf"?"CV":"Brev")+'</a>';});
      if(iv&&iv.forberedelse)lank.push('<a class="forb" href="'+encodeURI(iv.forberedelse)+'">Förberedelse</a>');
      else if(a.status==="intervju")lank.push('<button type="button" class="lank" data-kopiera="Förbered mig inför intervjun hos '+esc(a.bolag)+'.">Förbered med Claude</button>');
      return '<article class="ans'+(forf[a.mapp]?" forfallen":"")+'"><h4>'+esc(a.roll)+'</h4><div class="sub">'+esc(a.bolag)+'</div>'+
        (info.length?'<div class="sub">'+esc(info.join(" · "))+'</div>':'')+(lank.length?'<div class="lankar">'+lank.join("")+'</div>':'')+'</article>';
    }).join(""):'<div class="tomt">–</div>')+'</section>';
  }).join("")+'</div>';
})();

/* kalender */
var K=D.kalender;
$("n-kal").textContent=K.length||"";
$("p-kal").innerHTML=K.length?'<div class="card"><ul class="lista">'+K.map(function(h){
  var dd=dagar(h.datum), n=dd<0?"försenad":dd===0?"idag":dd===1?"i morgon":"om "+dd+" dagar";
  return '<li><div class="dag"><b>'+(+h.datum.slice(8))+'</b><span>'+MAN[+h.datum.slice(5,7)-1]+'</span></div><span class="prick p-'+h.typ+'" aria-hidden="true"></span><div class="t">'+esc(h.text)+'<small>'+n+'</small></div></li>';
}).join("")+'</ul></div>':tom("Inget inbokat","Sista ansökningsdagar och uppföljningar hamnar här.");

/* bevakning */
(function(){
  var B=D.bevakning, p=$("p-bev");
  function mat(u){if(!u)return '<span class="matare">–</span>';var pr=Math.round(100*u.bra/u.totalt);return '<span class="matare" title="'+u.bra+' av '+u.totalt+' intressanta">'+pr+' % träff<i style="--p:'+pr+'%"></i></span>';}
  var ny='<button type="button" class="btn" data-kopiera="Jag vill bevaka ett nytt ställe: ">'+IKON+'Bevaka ett nytt ställe</button>';
  if(!B.kallor.length&&!B.recept.length&&!B.hypoteser.length){p.innerHTML=tom("Ingen bevakning än","Berätta var du vill att vi letar, så håller Claude koll.","Hjälp mig bestämma var vi ska leta jobb.");return;}
  var kort1=function(rub,lista,rad,extra){return '<div class="card"><div class="bevhead"><h3 class="h2" style="margin:0">'+rub+'</h3>'+(extra||"")+'</div>'+(lista.length?'<ul>'+lista.map(rad).join("")+'</ul>':'<p class="sub" style="margin:0">Inga än.</p>')+'</div>';};
  p.innerHTML='<div class="bev">'+
    kort1("Källor",B.kallor,function(k){return '<li><div>'+esc(k.namn)+(k.egen?' <span class="tag joker">Din</span>':'')+(k.aktiv?'':' <span class="tag">Pausad</span>')+'<small>'+esc(k.senast?"Hämtad "+kort(k.senast):"Inte hämtad än")+'</small></div>'+mat(k.utbyte)+'</li>';},ny)+
    kort1("Sparade sökningar",B.recept,function(r){return '<li><div>'+esc(r.namn)+'<small>'+esc(r.q||"")+'</small></div>'+mat(r.utbyte)+'</li>';})+
    (B.hypoteser.length?kort1("Idéer vi prövar",B.hypoteser,function(h){return '<li><div>'+esc(h.text)+'<small>'+esc([h.metod,h.utfall].filter(Boolean).join(" · "))+'</small></div>'+mat(h.utbyte)+'</li>';}):'')+
  '</div>';
})();

/* flikar */
var tabs=[].slice.call(document.querySelectorAll('[role=tab]'));
function valj(t){tabs.forEach(function(x){var on=x===t;x.setAttribute("aria-selected",on);x.tabIndex=on?0:-1;$(x.getAttribute("aria-controls")).hidden=!on;});}
var h=location.hash.slice(1);tabs.forEach(function(t){if(h&&t.id==="t-"+h)valj(t);});
tabs.forEach(function(t,i){
  t.addEventListener("click",function(){valj(t);});
  t.addEventListener("keydown",function(e){var n=e.key==="ArrowRight"?1:e.key==="ArrowLeft"?-1:0;if(n){var x=tabs[(i+n+tabs.length)%tabs.length];valj(x);x.focus();e.preventDefault();}});
});

/* kopiera */
var toast=$("toast"),tt;
function visa(m){toast.textContent=m;toast.classList.add("syns");clearTimeout(tt);tt=setTimeout(function(){toast.classList.remove("syns");},2400);}
function fallback(t){var a=document.createElement("textarea");a.value=t;a.setAttribute("readonly","");a.style.position="fixed";a.style.opacity="0";document.body.appendChild(a);a.select();var ok=false;try{ok=document.execCommand("copy");}catch(e){}document.body.removeChild(a);return ok;}
document.addEventListener("click",function(e){
  var b=e.target.closest("[data-kopiera]");if(!b)return;
  var t=b.getAttribute("data-kopiera");
  var klar=function(){visa("Kopierat. Klistra in i chatten med Claude.");};
  if(navigator.clipboard&&window.isSecureContext!==false){navigator.clipboard.writeText(t).then(klar,function(){fallback(t)?klar():visa(t);});}
  else{fallback(t)?klar():visa(t);}
});
})();
