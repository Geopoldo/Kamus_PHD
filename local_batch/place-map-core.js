// Geographic counts are distinct PDF pages; co-mentions must share a reading.
var PlaceMapCore=(()=>{
 const key=p=>JSON.stringify([p.document_id,p.page]);
 const project=(lon,lat)=>[lon,-180/Math.PI*Math.log(Math.tan(Math.PI/4+Math.max(-85,Math.min(85,lat))*Math.PI/360))];
 const unproject=(x,y)=>[x,360/Math.PI*Math.atan(Math.exp(-y*Math.PI/180))-90];
 function zoomAt(bounds,factor,anchor=[bounds.x+bounds.w/2,bounds.y+bounds.h/2]){
  const w=Math.max(.04,Math.min(360,bounds.w*factor)),ratio=w/bounds.w;
  return {x:anchor[0]-(anchor[0]-bounds.x)*ratio,y:anchor[1]-(anchor[1]-bounds.y)*ratio,w,h:bounds.h*ratio};
 }
 function gesture(bounds,anchor,startMid,currentMid,ratio){
  const next=zoomAt(bounds,ratio,anchor),scale=next.w/bounds.w;
  next.x-=(currentMid[0]-startMid[0])*scale;next.y-=(currentMid[1]-startMid[1])*scale;return next;
 }
 const separate=(a,b)=>!(a.offsets||[]).some(([x,y])=>(b.offsets||[]).some(([s,e])=>x<e&&s<y));
 function build(catalog,rawPages,filteredPages,placeIds,qualities=[]){
  const all=new Map(catalog.map(e=>[e.id,e]));
  const rows=new Map(catalog.filter(e=>e.kind==='place'&&e.enabled!==false&&placeIds.has(e.id)).map(e=>[e.id,{entity:e,pages:new Map(),people:new Map()}]));
  const allowed=new Map(filteredPages.map(p=>[key(p),new Set(p.versions.map(v=>v.version))]));
  for(const p of rawPages){const versions=allowed.get(key(p));if(!versions)continue;
   for(const v of p.versions){if(!versions.has(v.version))continue;
    const matches=v.matches.filter(m=>!qualities.length||qualities.includes(m.quality));
    for(const [id,row] of rows){const places=matches.filter(m=>m.entity===id);if(!places.length)continue;
     if(!row.pages.has(key(p)))row.pages.set(key(p),{...p,versions:[]});
     row.pages.get(key(p)).versions.push({...v,matches});
     for(const m of matches){const e=all.get(m.entity);if(!e||!['person','surname'].includes(e.kind)||m.quality==='cooccurrence'||!places.some(place=>separate(place,m)))continue;
      if(!row.people.has(e.id))row.people.set(e.id,{entity:e,pages:new Set()});row.people.get(e.id).pages.add(key(p));
     }
    }
   }
  }
  return [...rows.values()].sort((a,b)=>b.pages.size-a.pages.size||a.entity.label.localeCompare(b.entity.label));
 }
 function location(entry,label){return entry&&entry.label===label&&!entry.needs_recheck&&['proposed','unconfirmed','confirmed'].includes(entry.status)&&Number.isFinite(entry.latitude)&&Math.abs(entry.latitude)<=90&&Number.isFinite(entry.longitude)&&Math.abs(entry.longitude)<=180?entry:null}
 function visible(entry,category){return !category||(category==='located'?!!entry:category==='unlocated'?!entry:entry?.status===category)}
 function filterRows(rows,{includeEmpty=false,category='',query=''}={},locations=new Map()){
  const normalize=text=>text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();
  const term=normalize(query.trim());
  return rows.filter(row=>(includeEmpty||row.pages.size>0)&&visible(locations.get(row.entity.id),category)&&(!term||normalize(row.entity.label).includes(term)));
 }
 function feature(row,entry){
  const p=location(entry,row.entity.label);
  return {type:'Feature',geometry:p?{type:'Point',coordinates:[p.longitude,p.latitude]}:null,properties:{
   entity_id:row.entity.id,referent:row.entity.label,priority:row.entity.priority,status:p?p.status:'unlocated',feature_name:p?.feature_name||'',
   source:entry?.source_url||'',note:entry?.note||'',reviewer:entry?.reviewer||'',updated:entry?.updated||null,pages:row.pages.size,
   references:[...row.pages.values()].map(p=>({folder:p.folder,document:p.document,page:p.page,versions:p.versions.map(v=>v.version)}))
  }};
 }
 return {build,project,unproject,zoomAt,gesture,location,visible,filterRows,feature};
})();
if(typeof module!=='undefined')module.exports=PlaceMapCore;
