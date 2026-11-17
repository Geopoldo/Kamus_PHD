/* Progress uses actual recorded states. No synthetic completion percentage. */
const GraphQueryProgress=(()=>{
 const active=new Set(['queued','waiting_pilot','waiting_gpu','embedding','query','preparing_results']);
 function describe(job){
  if(!job)return null;
  const phases=job.phases||[],phase=phases.at(-1)||{},global=job.mode==='global';
  let state=job.status;
  if(active.has(state)&&phase.status==='loading_model')state='loading_model';
  const stages=[{key:'saved',done:!!job.id},...(!global?[{key:'embedding',done:phases.some(p=>p.name==='embedding'&&p.status==='complete')}]:[]),{key:'query',done:phases.some(p=>p.name==='query'&&p.status==='complete')},{key:'results',done:job.status==='complete'}];
  const current=job.status==='complete'?'results':job.status==='preparing_results'?'results':phase.name==='embedding'?'embedding':phase.name==='query'?'query':'saved';
  return {state,active:active.has(job.status),waiting:['queued','waiting_pilot','waiting_gpu'].includes(state),failed:['failed','interrupted'].includes(job.status),current,stages,phase:phase.name,model:phase.model||null,
   waitRecorded:phases.some(p=>Number.isFinite(p.wait_seconds)),
   waitSeconds:phases.reduce((sum,p)=>sum+(p.wait_seconds||0),0),
   waitingSince:state==='waiting_gpu'?phase.started||job.started||job.created:null};
 }
 return {describe,isActive:status=>active.has(status)};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=GraphQueryProgress;

function graphQueryProgressView(host,actions){
 const card=gse('section');card.className='graph-query-progress';card.hidden=true;gAttr(card,'aria-label',gMsg('Estado de tu consulta'));
 const heading=gse('div');heading.className='graph-progress-heading';const indicator=gse('span');indicator.className='graph-progress-indicator';indicator.setAttribute('aria-hidden','true');
 const title=gse('strong');gAttr(title,'role','status');heading.append(indicator,title);
 const currentQuestion=gse('p');currentQuestion.className='graph-progress-question';
 const explanation=gse('p'),stages=gse('ol'),clock=gse('p'),connection=gse('small');stages.className='graph-progress-stages';clock.className='graph-progress-clock';clock.setAttribute('aria-live','off');connection.className='graph-progress-connection';
 const controls=gse('div');controls.className='priority-actions';const refresh=gButton(gMsg('Actualizar estado'),()=>actions.refresh()),telemetry=gButton(gMsg('Ver telemetría'),()=>value?.id&&actions.telemetry(value.id)),answer=gButton(gMsg('Ver respuesta ↓'),()=>actions.result(value.id));controls.append(refresh,telemetry,answer);
 card.append(heading,currentQuestion,explanation,stages,clock,connection,controls);host.append(card);
 let value=null,description=null,received=0,connected=false,lastState='';
 const labels={saved:gMsg('Pregunta guardada'),embedding:gMsg('Vector de la pregunta'),query:gMsg('Contexto y respuesta'),results:gMsg('Referencias y grafo')};
 const titles={queued:gMsg('Tu pregunta está en cola'),waiting_pilot:gMsg('Esperando a que termine el piloto'),waiting_gpu:gMsg('Esperando un turno de GPU'),loading_model:gMsg('Cargando el modelo local'),embedding:gMsg('Preparando la búsqueda por significado'),query:gMsg('Recuperando contexto y generando la respuesta'),preparing_results:gMsg('Preparando referencias y grafo'),complete:gMsg('Respuesta lista para consultar'),failed:gMsg('La consulta no pudo terminar'),interrupted:gMsg('La consulta se interrumpió')};
 const explanations={queued:gMsg('La pregunta ya está guardada. El trabajador local iniciará el proceso en cuanto esté disponible.'),waiting_pilot:gMsg('Primero debe terminar de construirse el índice del piloto. La pregunta permanece guardada.'),waiting_gpu:gMsg('La pregunta está guardada, pero todavía no se está generando una respuesta. Otro proceso local tiene el turno de GPU; la consulta continuará automáticamente cuando se libere.'),loading_model:gMsg('Se están cargando los pesos del modelo en la GPU. Después comenzará esta etapa de la consulta.'),embedding:gMsg('Qwen3-Embedding convierte tu pregunta en un vector para localizar entidades del piloto relacionadas con su significado.'),query:gMsg('Knowledge Graph recupera el contexto del piloto y Qwen genera una respuesta con ese material. Esta fase agrupa recuperación y generación; el motor no informa un porcentaje fiable.'),preparing_results:gMsg('La respuesta ya se generó. Se están vinculando sus referencias con las páginas de origen y preparando el grafo.'),complete:gMsg('Ya puedes leer la respuesta, explorar las relaciones recuperadas y abrir sus fuentes.'),failed:gMsg('El intento y sus registros se conservan. Revisa el mensaje y la telemetría; puedes volver a usar la pregunta para intentarlo de nuevo.'),interrupted:gMsg('El intento y sus registros se conservan. Puedes volver a usar la pregunta para iniciar otro intento.')};
 function tick(){if(!value||card.hidden)return;const now=Date.now()/1000,delta=description.active?Math.max(0,now-received):0,measured=value.elapsed_seconds??(value.finished&&value.started?value.finished-value.started:null),elapsed=description.active?(measured??Math.max(0,received-(value.started||value.created||received)))+delta:measured;
  const wait=description.waitingSince?description.waitSeconds+Math.max(0,received-description.waitingSince)+delta:description.waitRecorded||description.active?description.waitSeconds:null;
  gSet(clock,gMsg`Tiempo total: ${gTime(elapsed)} · Espera de GPU: ${gTime(wait)}`);
  const stale=!connected||(description.active&&now-received>15);
  card.dataset.stale=String(stale);
  gSet(connection,stale?gMsg('No se ha podido actualizar el estado. Esto no confirma que el proceso se haya detenido. Pulsa Actualizar estado.'):description.active?gMsg('Estado consultado cada 5 segundos. Puedes cambiar de pestaña; el proceso continúa.'):gMsg('Estado final registrado.'));
 }
 function update(job){value=job;description=GraphQueryProgress.describe(job);received=Date.now()/1000;connected=true;card.hidden=!job;if(!job)return;
  card.dataset.state=description.state;card.dataset.active=String(description.active);card.dataset.waiting=String(description.waiting);
  const signature=job.id+':'+description.state;if(signature!==lastState){gSet(title,titles[description.state]||gStatus(job.status));lastState=signature}
  gSet(currentQuestion,job.question||'');gSet(explanation,explanations[description.state]||'');
  stages.replaceChildren();for(const stage of description.stages){const item=gse('li');item.dataset.state=stage.done?'done':description.current===stage.key?'current':'pending';if(description.current===stage.key)item.setAttribute('aria-current','step');item.append(gse('span',stage.done?'✓':String(stages.children.length+1)),gse('span',labels[stage.key]));stages.append(item)}
  telemetry.hidden=!job.id;answer.hidden=job.status!=='complete';tick();
 }
 setInterval(()=>{if(!document.hidden)tick()},1000);
 return {update,disconnected(){connected=false;tick()},element:card};
}
if(typeof document!=='undefined'){
 const css=document.createElement('style');css.textContent=`.graph-query-progress{margin-top:18px;padding:20px;border:1px solid #bad1c7;border-left:4px solid #21786a;background:#edf4f0;border-radius:7px}.graph-progress-heading{display:flex;align-items:center;gap:12px;font-size:18px}.graph-progress-indicator{width:14px;height:14px;border:2px solid #a7bfb5;border-top-color:#21786a;border-radius:50%;flex-shrink:0}.graph-query-progress[data-active=true] .graph-progress-indicator{animation:graph-progress-spin 1.2s linear infinite}.graph-query-progress[data-waiting=true]{background:#fbf4e4;border-color:#d9b776}.graph-query-progress[data-state=failed],.graph-query-progress[data-state=interrupted]{background:#fff0ec;border-color:#c97960}.graph-query-progress[data-state=complete] .graph-progress-indicator{background:#21786a;border-color:#21786a}.graph-query-progress .graph-progress-question{font-weight:600;overflow-wrap:anywhere}.graph-progress-stages{display:flex;list-style:none;padding:0;gap:10px;flex-wrap:wrap;margin:18px 0}.graph-progress-stages li{display:flex;align-items:center;gap:8px;padding:9px 12px;border:1px solid #cad3cd;border-radius:5px;font-size:12px;background:#fffefa;color:#737773}.graph-progress-stages li[data-state=done]{color:#176d59;border-color:#93baa9}.graph-progress-stages li[data-state=current]{color:#202c25;border-color:#21786a;font-weight:700}.graph-progress-stages li>span:first-child{font-weight:700}.graph-query-progress .graph-progress-clock{font-size:13px;font-variant-numeric:tabular-nums;font-weight:600}.graph-progress-connection{display:block;font-size:11px;line-height:1.6}.graph-query-progress[data-stale=true] .graph-progress-connection{color:#9b4325}.graph-query-progress .priority-actions{margin:12px 0 0}.graph-query-progress .priority-actions button{font-size:12px;margin:0}@keyframes graph-progress-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.graph-query-progress[data-active=true] .graph-progress-indicator{animation:none}}`;document.head.append(css);
}
