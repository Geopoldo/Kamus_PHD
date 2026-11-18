// Local WebGL renderer. Layout changes never change the underlying evidence.
function graphWebGLMount({stage,svg,layout,colors,names,inspect,graph,details,onReset,onSelect,onZoom}){
 if(!window.MaphGraphEngine||!layout.nodes.length)return null;
 const {Graph,Sigma,EdgeArrowProgram}=window.MaphGraphEngine,network=new Graph({multi:true,type:'directed'});
 const tr=(es,en,fr)=>({es,en,fr})[uiLanguage]||es;
 const container=document.createElement('div');container.className='graph-webgl';container.tabIndex=0;
 container.setAttribute('aria-label',tr('Grafo interactivo. Escape o doble clic en el fondo para volver.','Interactive graph. Escape or double-click the background to return.','Graphe interactif. Échap ou double-clic sur le fond pour revenir.'));
 container.style.cssText='position:relative;width:100%;height:100%;min-height:560px;background:radial-gradient(ellipse at 40% 40%,#183331,#101719 75%);border-radius:12px;touch-action:none';stage.prepend(container);
 const responsive=gse('style');responsive.textContent='.graph-expanded .graph-webgl{min-height:240px!important;height:100%!important}.graph-expanded .graph-canvas-stage{min-height:240px!important}';details.append(responsive);
 const adjacent=new Map(layout.nodes.map(n=>[n.id,new Set()])),home=new Map(layout.nodes.map(n=>[n.id,{x:n.x,y:-n.y}]));
 for(const l of layout.links){adjacent.get(l.source).add(l.target);adjacent.get(l.target).add(l.source)}
 for(const n of layout.nodes)network.addNode(n.id,{...home.get(n.id),label:n.label,color:colors[n.type]||'#afbed1',size:Math.min(12,3+Math.sqrt(adjacent.get(n.id).size)*1.3)});
 layout.links.forEach((l,i)=>network.addEdgeWithKey(String(i),l.source,l.target,{type:'arrow',size:Math.min(3,.8+Math.log1p(l.edges.length)*.4),color:'#607c78',link:l}));
 let focus='',hover='',edgeFocus='',edgeHover='',openingEdge=false,matches=new Set(),visible=null,renderer,frame=0,dead=false,drag=null,suppressClickUntil=0;
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 const isRelated=id=>focus?id===focus||adjacent.get(focus)?.has(id):edgeFocus?network.extremities(edgeFocus).includes(id):!hover||id===hover||adjacent.get(hover)?.has(id);
 let labelBoxes=[];
 function label(ctx,data,settings,overlay=false){
  if(!data.label||!overlay&&(data.key===focus||data.key===hover))return;const size=14,full=String(data.label),text=full.length>34&&!overlay?full.slice(0,32)+'…':full;ctx.font='600 '+size+'px '+settings.labelFont;
  const w=Math.min(container.clientWidth-20,ctx.measureText(text).width),cw=container.clientWidth,ch=container.clientHeight;
  const candidates=[{x:data.x+data.size+7,y:data.y+5},{x:data.x-w-data.size-9,y:data.y+5},{x:data.x-w/2,y:data.y-data.size-12},{x:data.x-w/2,y:data.y+data.size+24}];
  let box;
  for(const candidate of candidates){const b={x:Math.max(6,Math.min(cw-w-8,candidate.x)),y:Math.max(20,Math.min(ch-8,candidate.y)),w:w+10,h:24,id:data.key};
   if(overlay||!labelBoxes.some(a=>a.id!==b.id&&b.x<a.x+a.w+4&&b.x+b.w+4>a.x&&b.y<a.y+a.h+4&&b.y+b.h+4>a.y)){box=b;break}}
  if(!box)return;labelBoxes.push(box);const {x,y}=box;
  ctx.fillStyle='#101b20';ctx.fillRect(x-4,y-size-3,w+10,size+10);ctx.fillStyle=data.color;ctx.fillRect(x-4,y-size-3,2,size+10);ctx.fillStyle='#f1f7f6';ctx.fillText(text,x,y,w);
 }

 try{renderer=new Sigma(network,container,{
  edgeProgramClasses:{arrow:EdgeArrowProgram},defaultEdgeType:'arrow',allowInvalidContainer:true,enableEdgeEvents:true,
  renderLabels:true,labelFont:'Manrope, sans-serif',labelSize:14,labelColor:{color:'#f1f7f6'},defaultDrawNodeLabel:label,defaultDrawNodeHover:(ctx,data,settings)=>label(ctx,data,settings,true),
  labelDensity:.4,labelGridCellSize:120,labelRenderedSizeThreshold:0,hideEdgesOnMove:false,zIndex:true,minCameraRatio:.04,maxCameraRatio:3,
  nodeReducer:(id,data)=>({...data,hidden:!!visible&&!visible.has(id),color:isRelated(id)&&(!matches.size||matches.has(id)||!!focus||!!edgeFocus)?data.color:'#354446',
   size:data.size+(id===focus||matches.has(id)?3:0),label:(id===focus||id===hover||matches.has(id)||visible||renderer&&renderer.getCamera().getState().ratio<.6)?data.label:'',
   forceLabel:id===focus||id===hover||(matches.size<12&&matches.has(id)),highlighted:id===focus||id===hover||matches.has(id),zIndex:id===focus?3:matches.has(id)?2:0}),
  edgeReducer:(id,data)=>{const [a,b]=network.extremities(id),selected=id===edgeFocus||id===edgeHover,incident=focus?(a===focus||b===focus):hover?(a===hover||b===hover):false;
   return {...data,hidden:!!visible&&(!visible.has(a)||!visible.has(b)),color:selected?'#ffd19b':incident?'#a6d6c9':focus||edgeFocus?'#344b49':'#546e6b',size:selected?Math.max(3,data.size):incident?Math.max(1.6,data.size):data.size,zIndex:selected?3:incident?2:0}}});
 }catch(error){container.remove();console.warn('WebGL unavailable; keeping SVG renderer',error);return null}
 renderer.on('beforeRender',()=>{labelBoxes=[]});
 for(const canvas of container.querySelectorAll('canvas')){canvas.style.margin='0';canvas.style.top='0';canvas.style.left='0';canvas.style.cursor='inherit'}
 svg.style.display='none';
 const camera=renderer.getCamera(),tooltip=stage.querySelector('.graph-edge-tooltip');
 // Freeze normalization while dragging/animating: moving one node must not move the camera.
 const homeBox=renderer.getBBox();renderer.setCustomBBox(homeBox);
 const guide=gse('div');guide.className='graph-visual-guide';guide.style.cssText='display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px;color:#e0eeeb;background:#15282b;border:1px solid #36534f;border-radius:10px;font-size:12px;line-height:1.6';
 const status=gse('span');status.setAttribute('role','status');status.style.cssText='flex:1 1 240px;font-weight:600';
 const mode=gButton(tr('Solo conexiones de la selección','Selected connections only','Connexions de la sélection'),()=>{if(!focus)return;if(visible){visible=null;moveTo(home,homeBox)}else focusView() ;updateStatus()});
 const back=gButton(tr('Volver al grafo completo','Return to full graph','Revenir au graphe complet'),()=>onReset?.());
 guide.append(status,mode,back);
 const instructions=gse('small',tr('Arrastra un nodo; arrastra una relación para mover sus extremos. Arrastra el fondo para recorrer. Doble clic en el fondo o Esc: deseleccionar y volver.','Drag a node; drag a relationship to move its endpoints. Drag the background to pan. Double-click the background or Esc: clear and return.','Glissez un nœud ; glissez un lien pour déplacer ses extrémités. Glissez le fond pour naviguer. Double-clic sur le fond ou Échap : effacer et revenir.'));
 instructions.style.cssText='flex-basis:100%;color:#bcd2cc';guide.append(instructions);stage.before(guide);
 const semantics=gse('small',tr('Cercanía = estructura de conexiones, no distancia geográfica ni certeza. Color = tipo · tamaño = vecinos · flecha = dirección · grosor = afirmaciones.','Proximity = connection structure, not geographic distance or certainty. Color = type · size = neighbors · arrow = direction · thickness = assertions.','Proximité = structure des liens, ni distance géographique ni certitude. Couleur = type · taille = voisins · flèche = direction · épaisseur = affirmations.'));semantics.style.cssText='display:block;color:#bcd2cc;padding:10px 0;font-size:11px';stage.after(semantics);
 function updateStatus(){
  mode.disabled=!focus;mode.setAttribute('aria-pressed',String(!!visible));
  status.textContent=focus?names.get(focus).label+' · '+(adjacent.get(focus).size-(adjacent.get(focus).has(focus)?1:0))+' '+tr('vecinos','neighbors','voisins'):edgeFocus?tr('Relación seleccionada','Selected relationship','Relation sélectionnée'):tr(`${layout.nodes.length} entidades · ${layout.links.length} conexiones`,`${layout.nodes.length} entities · ${layout.links.length} connections`,`${layout.nodes.length} entités · ${layout.links.length} connexions`);
  container.dataset.selection=focus||edgeFocus;container.dataset.view=visible?'neighborhood':'overview';
 }
 function boxFor(points){const xs=points.map(p=>p.x),ys=points.map(p=>p.y),pad=130;return {x:[Math.min(...xs)-pad,Math.max(...xs)+pad],y:[Math.min(...ys)-pad,Math.max(...ys)+pad]}}
 function cancelMotion(){if(frame)cancelAnimationFrame(frame);frame=0}
 function moveTo(target,box){
  cancelMotion();const starts=new Map([...target.keys()].map(id=>[id,{x:network.getNodeAttribute(id,'x'),y:network.getNodeAttribute(id,'y')}]));
  renderer.setCustomBBox(box);camera.animate({x:.5,y:.5,angle:0,ratio:visible?.82:1},{duration:reduced?0:350});
  const start=performance.now(),duration=reduced?0:420;
  function tick(now){if(dead)return;const t=duration?Math.min(1,(now-start)/duration):1,e=1-(1-t)**3;
   network.updateEachNodeAttributes((id,a)=>{const b=target.get(id),s=starts.get(id);return b?{...a,x:s.x+(b.x-s.x)*e,y:s.y+(b.y-s.y)*e}:a},{attributes:['x','y']});
   if(t<1)frame=requestAnimationFrame(tick);else{frame=0;renderer.refresh()}}
  frame=requestAnimationFrame(tick);
 }
 function focusView(){
  const points=GraphResultCore.focusLayout(layout,focus);visible=new Set(points.map(p=>p.id));hover='';
  moveTo(new Map(points.map(p=>[p.id,{x:p.x,y:-p.y}])),boxFor(points.map(p=>({x:p.x,y:-p.y}))));updateStatus();
 }
 function reset(){cancelMotion();focus=hover=edgeFocus=edgeHover='';visible=null;matches=new Set();tooltip.hidden=true;moveTo(home,homeBox);updateStatus()}
 camera.on('updated',()=>{onZoom?.(camera.getState().ratio);renderer.refresh()});
 renderer.on('enterNode',({node})=>{if(drag)return;hover=node;container.style.cursor='grab';renderer.refresh()});
 renderer.on('leaveNode',()=>{if(drag)return;hover='';container.style.cursor='';renderer.refresh()});
 renderer.on('clickNode',({node,event})=>{if(performance.now()<suppressClickUntil){event.preventSigmaDefault();return}onSelect?.(node)});
 function edgeTooltip(edge,event){
  if(drag)return;edgeHover=edge;const l=network.getEdgeAttribute(edge,'link');tooltip.replaceChildren(gse('strong',names.get(l.source).label+' → '+names.get(l.target).label));
  for(const e of l.edges.slice(0,5))tooltip.append(gse('p',e.fields?.relation||gMsg('Relación candidata')),gse('small',e.page.document+' · p. '+e.page.page));
  if(l.edges.length>5)tooltip.append(gse('small','+ '+(l.edges.length-5)));tooltip.hidden=false;
  tooltip.style.left=Math.max(8,Math.min(container.clientWidth-tooltip.offsetWidth-8,event.x+12))+'px';tooltip.style.top=Math.max(8,Math.min(container.clientHeight-tooltip.offsetHeight-8,event.y+12))+'px';renderer.refresh();
 }
 renderer.on('enterEdge',({edge,event})=>{container.style.cursor='grab';edgeTooltip(edge,event)});
 renderer.on('leaveEdge',()=>{edgeHover='';tooltip.hidden=true;if(!drag)container.style.cursor='';renderer.refresh()});
 function selectEdge(edge,event){if(performance.now()<suppressClickUntil){event.preventSigmaDefault();return}const l=network.getEdgeAttribute(edge,'link');tooltip.hidden=true;
  // Keep the current viewport when opening an edge's evidence.
  openingEdge=true;try{inspect(names.get(l.source).label+' → '+names.get(l.target).label,l.edges)}finally{openingEdge=false}edgeFocus=edge;updateStatus();renderer.refresh()}
 renderer.on('clickEdge',({edge,event})=>selectEdge(edge,event));
 renderer.on('doubleClickStage',({event})=>{event.preventSigmaDefault();onReset?.()});
 container.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();onReset?.()}});
 function startDrag(ids,event){
  if(event.original?.button!=null&&event.original.button!==0)return;
  cancelMotion();tooltip.hidden=true;const p=renderer.viewportToGraph(event);
  drag={ids:[...new Set(ids)],start:p,pixel:{x:event.x,y:event.y},positions:new Map(network.nodes().map(id=>[id,{x:network.getNodeAttribute(id,'x'),y:network.getNodeAttribute(id,'y')}])),moved:false};
  container.dataset.gesture=ids.length===1?'node-drag':'edge-drag';container.style.cursor='grabbing';event.preventSigmaDefault();
 }
 renderer.on('downNode',({node,event})=>startDrag([node],event));
 renderer.on('downEdge',({edge,event})=>startDrag(network.extremities(edge),event));
 // GPU picking hits the thin painted line. Give links a forgiving 7px hit area
 // on the background as well, without widening every line in a dense overview.
 let screenPositions=null;
 renderer.on('afterRender',()=>{screenPositions=null});
 function screenNodes(){
  if(!screenPositions){screenPositions=new Map();network.forEachNode((id,a)=>{if(!visible||visible.has(id))screenPositions.set(id,renderer.graphToViewport(a))})}
  return screenPositions;
 }
 function nearestNode(event){let best='',distance=13;for(const [id,p] of screenNodes()){const d=Math.hypot(event.x-p.x,event.y-p.y);if(d<distance){distance=d;best=id}}return best}
 function nearestEdge(event){
  screenNodes();
  let best='',distance=7;
  network.forEachEdge((id,a,source,target)=>{const p=screenPositions.get(source),q=screenPositions.get(target);if(!p||!q||source===target)return;
   const dx=q.x-p.x,dy=q.y-p.y,len=dx*dx+dy*dy;if(!len)return;const t=Math.max(0,Math.min(1,((event.x-p.x)*dx+(event.y-p.y)*dy)/len));
   // Endpoints belong to nodes, even just outside their painted disc.
   if(Math.hypot(event.x-p.x,event.y-p.y)<12||Math.hypot(event.x-q.x,event.y-q.y)<12)return;
   const d=Math.hypot(event.x-p.x-t*dx,event.y-p.y-t*dy);if(d<distance){distance=d;best=id}
  });return best;
 }
 renderer.on('downStage',({event})=>{container.dataset.gesture='pan';const node=nearestNode(event);if(node){startDrag([node],event);return}const edge=nearestEdge(event);if(edge)startDrag(network.extremities(edge),event)});
 renderer.on('clickStage',({event})=>{if(performance.now()<suppressClickUntil)return;const node=nearestNode(event);if(node){onSelect?.(node);return}const edge=nearestEdge(event);if(edge)selectEdge(edge,event)});
 const captor=renderer.getMouseCaptor();
 function moveDrag(event){
  if(!drag)return;event.preventSigmaDefault();event.original?.preventDefault();
  if(!drag.moved&&Math.hypot(event.x-drag.pixel.x,event.y-drag.pixel.y)<4)return;
  drag.moved=true;const p=renderer.viewportToGraph(event),dx=p.x-drag.start.x,dy=p.y-drag.start.y,held=new Set(drag.ids),influenced=new Set(drag.ids.flatMap(id=>[...adjacent.get(id)]));
  // Neighbors follow gently; held nodes track the mouse exactly. This deforms
  // the local network without a perpetual simulation or changes to evidence.
  network.updateEachNodeAttributes((id,a)=>{const influence=held.has(id)?1:influenced.has(id)&&(!visible||visible.has(id))?.16:0,s=drag.positions.get(id);return influence?{...a,x:s.x+dx*influence,y:s.y+dy*influence}:a},{attributes:['x','y']});
 }
 function endDrag(){if(!drag)return;if(drag.moved)suppressClickUntil=performance.now()+300;drag=null;container.style.cursor='';renderer.refresh()}
 function hoverLink(event){if(drag)return;const node=nearestNode(event);if(hover!==node){hover=node;renderer.refresh()}if(node){tooltip.hidden=true;container.style.cursor='grab';return}const edge=nearestEdge(event);if(edge){container.style.cursor='grab';if(edge!==edgeHover)edgeTooltip(edge,event)}else if(edgeHover){edgeHover='';tooltip.hidden=true;container.style.cursor='';renderer.refresh()}}
 captor.on('mousemovebody',moveDrag);captor.on('mousemove',hoverLink);captor.on('mouseup',endDrag);window.addEventListener('blur',endDrag);
 let dimensions=[container.clientWidth,container.clientHeight];
 const resize=new ResizeObserver(()=>{if(details.isConnected&&container.clientWidth&&container.clientHeight){
  const changed=dimensions[0]!==container.clientWidth||dimensions[1]!==container.clientHeight;dimensions=[container.clientWidth,container.clientHeight];
  renderer.resize();if(changed)camera.setState({x:.5,y:.5,angle:0,ratio:visible?.82:1});renderer.refresh();
 }});resize.observe(container);
 const observer=new MutationObserver(()=>{if(!details.isConnected){dead=true;cancelMotion();window.removeEventListener('blur',endDrag);captor.off('mousemovebody',moveDrag);captor.off('mousemove',hoverLink);captor.off('mouseup',endDrag);renderer.kill();resize.disconnect();observer.disconnect()}});observer.observe(document.body,{childList:true,subtree:true});
 updateStatus();
 return {
  highlight(id,ids){const changed=focus!==(id||'');focus=id||'';matches=ids||new Set();edgeFocus='';if(changed&&focus)focusView();else if(changed&&visible&&!openingEdge){visible=null;moveTo(home,homeBox)}updateStatus();renderer.refresh()},
  focusMatches(ids){focus=hover=edgeFocus='';matches=new Set(ids);visible=new Set(matches);for(const id of matches)for(const neighbor of adjacent.get(id)||[])visible.add(neighbor);if(!visible.size){renderer.refresh();updateStatus();return}const points=[...visible].filter(id=>home.has(id)).map(id=>({id,...home.get(id)}));moveTo(new Map(points.map(p=>[p.id,{x:p.x,y:p.y}])),boxFor(points));updateStatus();status.textContent=matches.size+' '+tr('correspondencias y todas sus conexiones directas','matches and all their direct connections','correspondances et toutes leurs connexions directes');renderer.refresh()},
  reset,zoom(factor){camera.animate({ratio:camera.getBoundedRatio(camera.getState().ratio*factor)},{duration:reduced?0:200})},
  bounds(b,initial){camera.animate({ratio:b.w/initial.w},{duration:reduced?0:200})}
 };
}
