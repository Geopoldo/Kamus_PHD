// Pointer gestures keep their geographic anchor; no remote map library is required.
function placeMapNavigation(svg,read,write,navigation=PlaceMapCore){
 const pointers=new Map();let start=null,frame=0,next=null,moved=false;
 const coords=(event,matrix=svg.getScreenCTM().inverse())=>{const p=svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;const q=p.matrixTransform(matrix);return [q.x,q.y]};
 const midpoint=items=>({clientX:items.reduce((s,p)=>s+p.clientX,0)/items.length,clientY:items.reduce((s,p)=>s+p.clientY,0)/items.length});
 const distance=items=>items.length<2?0:Math.hypot(items[0].clientX-items[1].clientX,items[0].clientY-items[1].clientY);
 function update(value){next=value;if(!frame)frame=requestAnimationFrame(()=>{frame=0;if(svg.isConnected&&next)write(next);next=null})}
 function flush(){if(frame)cancelAnimationFrame(frame);frame=0;if(next&&svg.isConnected)write(next);next=null}
 function begin(){flush();const items=[...pointers.values()];if(!items.length){start=null;return}const matrix=svg.getScreenCTM().inverse(),mid=coords(midpoint(items),matrix);start={bounds:{...read()},matrix,mid,distance:distance(items)};}
 svg.addEventListener('wheel',event=>{event.preventDefault();flush();const delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?svg.clientHeight:1);update(navigation.zoomAt(read(),Math.exp(Math.max(-.65,Math.min(.65,delta*.0015))),coords(event)))},{passive:false});
 svg.addEventListener('dblclick',event=>{if(event.target.closest('.geo-marker,[role=button]'))return;event.preventDefault();flush();update(navigation.zoomAt(read(),.5,coords(event)))});
 svg.addEventListener('pointerdown',event=>{if(event.button!==0&&event.pointerType==='mouse')return;pointers.set(event.pointerId,{clientX:event.clientX,clientY:event.clientY});moved=false;begin();if(!event.target.closest('.geo-marker,[role=button]')||pointers.size>1)svg.setPointerCapture(event.pointerId)});
 svg.addEventListener('pointermove',event=>{if(!pointers.has(event.pointerId)||!start)return;pointers.set(event.pointerId,{clientX:event.clientX,clientY:event.clientY});const items=[...pointers.values()],mid=coords(midpoint(items),start.matrix),distanceNow=distance(items);const drift=Math.hypot(mid[0]-start.mid[0],mid[1]-start.mid[1]);if(!moved&&drift<start.bounds.w/500&&Math.abs(distanceNow-start.distance)<3)return;moved=true;const ratio=start.distance&&distanceNow?start.distance/distanceNow:1;update(navigation.gesture(start.bounds,start.mid,start.mid,mid,ratio));});
 function end(event){if(!pointers.has(event.pointerId))return;flush();pointers.delete(event.pointerId);if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);begin()}
 svg.addEventListener('pointerup',end);svg.addEventListener('pointercancel',end);
 svg.addEventListener('click',event=>{if(moved){event.preventDefault();event.stopImmediatePropagation();moved=false}},true);
 svg.addEventListener('keydown',event=>{if(event.target!==svg)return;const key=event.key;if(!['+','=','-','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(key))return;event.preventDefault();flush();let b={...read()};if(key==='+'||key==='=')b=navigation.zoomAt(b,.6);else if(key==='-')b=navigation.zoomAt(b,1.6);else{if(key==='ArrowLeft')b.x-=b.w*.15;if(key==='ArrowRight')b.x+=b.w*.15;if(key==='ArrowUp')b.y-=b.h*.15;if(key==='ArrowDown')b.y+=b.h*.15}write(b)});
 return ()=>{if(frame)cancelAnimationFrame(frame)};
}
