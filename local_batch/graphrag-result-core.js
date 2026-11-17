// Deterministic overview: retain every node, isolated component and assertion.
(function(root){
 function overview(graph,options={}){
  const nodes=new Map(graph.nodes.map(n=>[n.id,{...n}])),links=new Map(),adj=new Map();
  for(const n of nodes.values())adj.set(n.id,new Set());
  for(const edge of graph.relationships){
   for(const id of [edge.source,edge.target])if(!nodes.has(id)){nodes.set(id,{id,label:id,type:'UNKNOWN'});adj.set(id,new Set())}
   adj.get(edge.source).add(edge.target);adj.get(edge.target).add(edge.source);
   const key=JSON.stringify([edge.source,edge.target]);if(!links.has(key))links.set(key,{source:edge.source,target:edge.target,edges:[]});links.get(key).edges.push(edge);
  }
  const visited=new Set(),components=[];
  for(const id of nodes.keys()){if(visited.has(id))continue;const queue=[id],component=[];visited.add(id);for(let i=0;i<queue.length;i++){const item=queue[i];component.push(item);for(const other of adj.get(item))if(!visited.has(other)){visited.add(other);queue.push(other)}}components.push(component)}
  components.sort((a,b)=>b.length-a.length);
  // Separate disconnected components into cells. All positions stay in the frame.
  const columns=Math.max(1,Math.ceil(Math.sqrt(components.length*1.5))),rows=Math.max(1,Math.ceil(components.length/columns));
  const cellW=Math.max(300,Math.sqrt(components[0]?.length||1)*85),cellH=Math.max(240,cellW*.75),width=Math.max(900,columns*cellW),height=Math.max(560,rows*cellH);
  if(!options.compact)components.forEach((component,index)=>{
   const w=width/columns,h=height/rows,cx=(index%columns+.5)*w,cy=(Math.floor(index/columns)+.5)*h;
   const points=component.map((id,i)=>({id,x:cx+Math.cos(i*2.39996)*Math.sqrt((i+.5)/component.length)*w*.34,y:cy+Math.sin(i*2.39996)*Math.sqrt((i+.5)/component.length)*h*.34}));
   const byId=new Map(points.map(p=>[p.id,p]));
   for(let step=0;step<160;step++){
    const force=new Map(points.map(p=>[p.id,{x:(cx-p.x)*.008,y:(cy-p.y)*.008}]));
    for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){const a=points[i],b=points[j],dx=a.x-b.x,dy=a.y-b.y,d=Math.max(1,Math.hypot(dx,dy)),f=Math.min(20,7000/(d*d));force.get(a.id).x+=dx/d*f;force.get(a.id).y+=dy/d*f;force.get(b.id).x-=dx/d*f;force.get(b.id).y-=dy/d*f}
    for(const p of points)for(const other of adj.get(p.id)){if(other===p.id)continue;const q=byId.get(other),dx=q.x-p.x,dy=q.y-p.y,d=Math.max(1,Math.hypot(dx,dy)),f=(d-110)*.017;force.get(p.id).x+=dx/d*f;force.get(p.id).y+=dy/d*f}
    for(const p of points){const f=force.get(p.id),cool=1-step/180;p.x=Math.max(cx-w/2+85,Math.min(cx+w/2-85,p.x+Math.max(-10,Math.min(10,f.x))*cool));p.y=Math.max(cy-h/2+40,Math.min(cy+h/2-45,p.y+Math.max(-10,Math.min(10,f.y))*cool))}
   }
   for(const p of points)Object.assign(nodes.get(p.id),p);
  });
  if(options.compact){
   // Pack disconnected components by their size. A singleton must not consume
   // the same area as the largest component; every entity remains represented.
   const isolated=components.filter(c=>c.length===1&&!adj.get(c[0]).size).flat(),connected=components.filter(c=>c.length>1||adj.get(c[0]).size);
   const W=2160,H=1440,top=isolated.length?1130:H,groups=connected.map(ids=>({ids,weight:Math.max(4,ids.length)}));
   function spread(ids,x,y,w,h){
    // Solve directly in each component's allotted space. Scaling a dense cloud
    // down after simulation used to compress the largest component into a knot.
    const points=ids.map((id,i)=>({id,x:x+w/2+Math.cos(i*2.39996)*Math.sqrt((i+.5)/ids.length)*w*.4,y:y+h/2+Math.sin(i*2.39996)*Math.sqrt((i+.5)/ids.length)*h*.4})),byId=new Map(points.map(p=>[p.id,p]));
    const spacing=Math.max(28,Math.min(110,Math.sqrt(w*h/ids.length)*.7));
    for(let step=0;step<260;step++){
     const force=new Map(points.map(p=>[p.id,{x:(x+w/2-p.x)*.012,y:(y+h/2-p.y)*.012}]));
     for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){
      const a=points[i],b=points[j],dx=a.x-b.x,dy=a.y-b.y,d=Math.max(.01,Math.hypot(dx,dy)),f=Math.min(24,spacing*spacing*4/(d*d));
      force.get(a.id).x+=dx/d*f;force.get(a.id).y+=dy/d*f;force.get(b.id).x-=dx/d*f;force.get(b.id).y-=dy/d*f;
     }
     for(const p of points)for(const other of adj.get(p.id)){if(other===p.id)continue;const q=byId.get(other),dx=q.x-p.x,dy=q.y-p.y,d=Math.max(1,Math.hypot(dx,dy)),f=(d-spacing*1.8)*.014;force.get(p.id).x+=dx/d*f;force.get(p.id).y+=dy/d*f}
     for(const p of points){const f=force.get(p.id),cool=.2+.8*(1-step/260);p.x=Math.max(x+24,Math.min(x+w-24,p.x+Math.max(-12,Math.min(12,f.x))*cool));p.y=Math.max(y+24,Math.min(y+h-24,p.y+Math.max(-12,Math.min(12,f.y))*cool))}
    }
    // A final collision pass preserves distinguishable clickable nodes.
    for(let pass=0;pass<35;pass++)for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){const a=points[i],b=points[j],dx=b.x-a.x,dy=b.y-a.y,d=Math.max(.01,Math.hypot(dx,dy)),minimum=Math.min(36,spacing*.65);if(d<minimum){const push=(minimum-d)/2;for(const [p,sign]of [[a,-1],[b,1]]){p.x=Math.max(x+20,Math.min(x+w-20,p.x+sign*dx/d*push));p.y=Math.max(y+20,Math.min(y+h-20,p.y+sign*dy/d*push))}}}
    for(const p of points)Object.assign(nodes.get(p.id),p);
   }
   function pack(items,x,y,w,h){
    if(!items.length)return;
    if(items.length===1){spread(items[0].ids,x,y,w,h);return}
    const total=items.reduce((n,g)=>n+g.weight,0);let n=1,sum=items[0].weight;while(n<items.length-1&&sum+items[n].weight<=total/2){sum+=items[n].weight;n++}const fraction=sum/total;
    if(w>=h){pack(items.slice(0,n),x,y,w*fraction,h);pack(items.slice(n),x+w*fraction,y,w*(1-fraction),h)}else{pack(items.slice(0,n),x,y,w,h*fraction);pack(items.slice(n),x,y+h*fraction,w,h*(1-fraction))}
   }
   pack(groups,20,20,W-40,top-40);
   if(isolated.length){const cols=Math.ceil(Math.sqrt(isolated.length*W/(H-top-45))),rows=Math.ceil(isolated.length/cols),dx=(W-60)/cols,dy=(H-top-60)/rows;isolated.forEach((id,i)=>Object.assign(nodes.get(id),{x:30+(i%cols+.5)*dx,y:top+45+(Math.floor(i/cols)+.5)*dy}))}
   return {nodes:[...nodes.values()],links:[...links.values()],width:W,height:H,components:components.length,isolatedRegion:isolated.length?{x:20,y:top,width:W-40,height:H-top-15,count:isolated.length}:null};
  }
  return {nodes:[...nodes.values()],links:[...links.values()],width,height,components:components.length};
 }
 function zoomAt(bounds,factor,anchor=[bounds.x+bounds.w/2,bounds.y+bounds.h/2]){
  const w=Math.max(40,Math.min(50000,bounds.w*factor)),scale=w/bounds.w;
  return {x:anchor[0]-(anchor[0]-bounds.x)*scale,y:anchor[1]-(anchor[1]-bounds.y)*scale,w,h:bounds.h*scale};
 }
 function gesture(bounds,anchor,start,end,ratio){const next=zoomAt(bounds,ratio,anchor),scale=next.w/bounds.w;next.x-=(end[0]-start[0])*scale;next.y-=(end[1]-start[1])*scale;return next}
 function labelIds(nodes,bounds,initialWidth,searchIds=new Set(),screenWidth=1000){
  // Labels are contextual: none at overview scale, no hover exception.
  const zoomed=initialWidth/bounds.w>=1.8,visible=new Set(),boxes=[],scale=screenWidth/bounds.w;
  for(const n of [...nodes].sort((a,b)=>Number(searchIds.has(b.id))-Number(searchIds.has(a.id)))){
   if(!zoomed&&!searchIds.has(n.id))continue;
   if(n.x<bounds.x||n.x>bounds.x+bounds.w||n.y<bounds.y||n.y>bounds.y+bounds.h)continue;
   const width=Math.min(25,n.label.length)*7,px=(n.x-bounds.x)*scale,py=(n.y-bounds.y)*scale+18,box={x:px-width/2,y:py,w:width,h:16};
   if(boxes.some(b=>box.x<b.x+b.w+8&&box.x+box.w+8>b.x&&box.y<b.y+b.h+4&&box.y+box.h+4>b.y))continue;
   boxes.push(box);visible.add(n.id);
  }
  return visible;
 }
 function matchesSource(page,filters={}){const folder=page.folder||'';return (!(filters.folders||[]).length||filters.folders.some(f=>folder===f||folder.startsWith(f+'/')))&&(!(filters.documents||[]).length||filters.documents.includes(page.document))}
 function filterSources(graph,filters={}){
  if(!(filters.folders||[]).length&&!(filters.documents||[]).length)return graph;
  const relationships=graph.relationships.filter(e=>matchesSource(e.page,filters)),ends=new Set(relationships.flatMap(e=>[e.source,e.target]));
  const nodes=graph.nodes.map(n=>({...n,mentions:(n.mentions||[]).filter(m=>matchesSource(m.page,filters))})).filter(n=>n.mentions.length||ends.has(n.id));
  const selection=(graph.selection||[]).filter(p=>matchesSource(p,filters)),entity_counts={};for(const n of nodes)entity_counts[n.type]=(entity_counts[n.type]||0)+1;
  const evidence_counts={total:relationships.length,quotes_found:relationships.filter(e=>e.quote_status==='found').length,quotes_pending:relationships.filter(e=>e.quote_status!=='found').length,human_validated:0,entity_pairs:new Set(relationships.map(e=>JSON.stringify([e.source,e.target]))).size,pages_with_relationships:new Set(relationships.map(e=>JSON.stringify([e.page.document_id,e.page.page]))).size};
  for(const field of ['event_time','document_time'])evidence_counts[field+'_identified']=relationships.filter(e=>e.fields?.[field]&&e.fields[field].toLowerCase()!=='unknown').length;
  return {...graph,nodes,relationships,selection,pages:selection.length,source_documents:new Set(selection.map(p=>p.document)).size,entity_counts,evidence_counts,communities:[],query:null,spot_checks:null,rejected_candidates:[],source_filters:filters};
 }
 const api={overview,zoomAt,gesture,labelIds,matchesSource,filterSources};if(typeof module!=='undefined')module.exports=api;else root.GraphResultCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
