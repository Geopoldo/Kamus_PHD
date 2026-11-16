// Counts are distinct source document/page pairs. Versions never inflate page totals.
var PriorityBalance = (() => {
  const ranks = {literal:0,alias:1,near:2,candidate:3,cooccurrence:4,clue:5};
  const groups = ['strong','review','context','none'];
  const scores=[100,95,85,60,20,20];
  const group = rank => rank < 2 ? 'strong' : rank < 4 ? 'review' : rank < 6 ? 'context' : 'none';
  const pageKey = p => JSON.stringify([p.document_id,p.page]);
  // Empty selections leave a dimension unrestricted; options within it are OR.
  const filterChoice=(selection,value)=>!selection?.length||selection.includes(value);
  function filterEntities(entities,f={}){
    return entities.filter(e=>e.enabled!==false&&filterChoice(f.kind,e.kind)&&filterChoice(f.priority,e.priority)&&filterChoice(f.refs,e.id)&&(!f.sheet?.length||(e.sources||[]).some(s=>f.sheet.includes(s.sheet))||(f.sheet.includes('user')&&!(e.sources||[]).length)));
  }
  function filterSource(source,f={}){
    return filterChoice(f.folder,source.folder)&&filterChoice(f.document,source.document)&&filterChoice(f.version,source.version?.startsWith('second_reading:')?'secondary':source.version);
  }
  function filterEvidence(pages,f={},valid=null){
    return pages.filter(p=>filterChoice(f.folder,p.folder)&&filterChoice(f.document,p.document)).map(p=>({...p,versions:p.versions.filter(v=>filterSource({...p,version:v.version},f)).map(v=>({...v,matches:v.matches.filter(m=>(!valid||valid.has(m.entity))&&filterChoice(f.quality,m.quality))})).filter(v=>v.matches.length)})).filter(p=>p.versions.length);
  }
  function relevance(matches,entities){
    let best=99;
    for(const m of matches){const e=entities.get(m.entity);if(!e)continue;const rank=ranks[m.quality]??99;
      // Full or nearby personal names precede families/places. Distant words are last.
      const value=e.kind==='person'?(rank<4?rank:rank===4?6:99):(rank<3?4:rank<6?5:99);
      best=Math.min(best,value);
    }
    return best;
  }
  function recordRelevance(s){return relevance([...s.records.values()].flatMap(p=>[...p.versions.values()].flatMap(v=>[...v.matches])).filter(m=>m.entity===s.entity.id),new Map([[s.entity.id,s.entity]]));}
  const record = () => ({records:new Map(),pageRanks:new Map(),documents:new Set(),readings:new Set(),occurrences:0,best:99});
  function add(target,p,v,matches,rank,count=matches.length){
    const key=pageKey(p);target.best=Math.min(target.best,rank);
    target.pageRanks.set(key,Math.min(target.pageRanks.get(key)??99,rank));target.documents.add(p.document_id);
    target.readings.add(JSON.stringify([key,v.version]));target.occurrences+=count;
    if(!target.records.has(key))target.records.set(key,{page:p,versions:new Map()});
    const row=target.records.get(key);
    if(!row.versions.has(v.version))row.versions.set(v.version,{version:v,matches:new Set()});
    for(const m of matches)row.versions.get(v.version).matches.add(m);
  }
  function count(target){
    const byGroup={strong:0,review:0,context:0,none:0};
    for(const rank of target.pageRanks.values())byGroup[group(rank)]++;
    return {pages:target.pageRanks.size,documents:target.documents.size,readings:target.readings.size,
            occurrences:target.occurrences,best:target.best,group:group(target.best),byGroup,
            closePages:[...target.pageRanks.values()].filter(r=>r<4).length,
            distantPages:[...target.pageRanks.values()].filter(r=>r===4).length,
            score:[...target.pageRanks.values()].reduce((sum,r)=>sum+(scores[r]||0),0)};
  }
  function materialize(target){
    if(!target)return [];
    return [...target.records.values()].map(r=>({...r.page,versions:[...r.versions.values()].map(v=>({...v.version,matches:[...v.matches]}))}))
      .sort((a,b)=>a.document.localeCompare(b.document)||a.page-b.page);
  }
  function audit(catalog){
    return catalog.sheets.map(s=>{const rows=new Set(catalog.entities.flatMap(e=>e.sources.filter(x=>x.sheet===s.name).map(x=>x.row)));
      return {sheet:s.name,expected:s.data_rows,covered:rows.size,complete:rows.size===s.data_rows};});
  }
  function analyze(entities,pages){
    const stats=new Map(entities.map(e=>[e.id,{entity:e,...record()}])),total=record();
    for(const p of pages)for(const v of p.versions){
      const byEntity=new Map();
      for(const m of v.matches)if(stats.has(m.entity)){
        if(!byEntity.has(m.entity))byEntity.set(m.entity,[]);byEntity.get(m.entity).push(m);
      }
      for(const [id,matches] of byEntity){const rank=Math.min(...matches.map(m=>ranks[m.quality]??99));add(stats.get(id),p,v,matches,rank);}
      const all=[...byEntity.values()].flat();if(all.length)add(total,p,v,all,Math.min(...all.map(m=>ranks[m.quality]??99)));
    }
    const breakdown={};for(const kind of ['person','surname','place','total'])breakdown[kind]={total:0,strong:0,review:0,context:0,none:0};
    for(const s of stats.values())for(const kind of [s.entity.kind,'total']){breakdown[kind].total++;breakdown[kind][group(s.best)]++;}
    const byPriority={};for(const s of stats.values()){const key=s.entity.priority||'Baja';if(!byPriority[key])byPriority[key]={total:0,strong:0,review:0,context:0,none:0};byPriority[key].total++;byPriority[key][group(s.best)]++;}
    return {stats,total,breakdown,byPriority};
  }
  function column(p,v,m,axis){return axis==='document'?p.document:axis==='version'?v.version:axis==='quality'?m.quality:p.folder;}
  function buildMatrix(entities,pages,axis='folder',options={}){
    const cells=new Map(entities.map(e=>[e.id,new Map()])),stats=new Map(entities.map(e=>[e.id,{entity:e,...record()}]));
    const columns=new Set(options.columns||[]),valid=new Set(entities.map(e=>e.id));
    function put(id,key,p,v,matches,rank,count){
      columns.add(key);const row=cells.get(id);if(!row.has(key))row.set(key,record());add(row.get(key),p,v,matches,rank,count);
    }
    for(const p of pages)for(const v of p.versions){
      if(options.focus){
        // Pair evidence must coexist in one version, and normally use separate text spans.
        const focus=v.matches.filter(m=>m.entity===options.focus);if(!focus.length)continue;
        const byEntity=new Map();for(const m of v.matches)if(m.entity!==options.focus&&valid.has(m.entity)){
          const paired=focus.filter(a=>options.includeOverlap||!a.offsets.some(([x,y])=>m.offsets.some(([s,e])=>x<e&&s<y)));
          if(!paired.length)continue;
          const rank=Math.min(...paired.map(a=>Math.max(ranks[a.quality]??99,ranks[m.quality]??99)));
          if(!byEntity.has(m.entity))byEntity.set(m.entity,{rank:99,matches:new Set()});
          const hit=byEntity.get(m.entity);hit.rank=Math.min(hit.rank,rank);hit.matches.add(m);paired.forEach(a=>hit.matches.add(a));
        }
        for(const [id,hit] of byEntity){
          const matches=[...hit.matches],quality=Object.keys(ranks).find(q=>ranks[q]===hit.rank)||'clue';
          put(id,column(p,v,{quality},axis),p,v,matches,hit.rank,1);add(stats.get(id),p,v,matches,hit.rank,1);
        }
      }else{
        const byEntity=new Map();for(const m of v.matches)if(valid.has(m.entity)){
          const rank=ranks[m.quality]??99;put(m.entity,column(p,v,m,axis),p,v,[m],rank,1);
          if(!byEntity.has(m.entity))byEntity.set(m.entity,[]);byEntity.get(m.entity).push(m);
        }
        for(const [id,matches] of byEntity)add(stats.get(id),p,v,matches,Math.min(...matches.map(m=>ranks[m.quality]??99)));
      }
    }
    if(options.focus){cells.delete(options.focus);stats.delete(options.focus);}
    return {cells,stats,columns:[...columns].sort((a,b)=>a.localeCompare(b))};
  }
  function buildCross(people,places,pages,options={}){
    const cells=new Map(people.map(e=>[e.id,new Map()])),stats=new Map(people.map(e=>[e.id,{entity:e,...record()}]));
    const wanted=new Map([...people,...places].map(e=>[e.id,e]));
    const eligible=pages.map(p=>({...p,versions:p.versions.map(v=>({...v,matches:v.matches.filter(m=>wanted.has(m.entity)&&!(options.closeNames!==false&&wanted.get(m.entity).kind==='person'&&m.quality==='cooccurrence'))})).filter(v=>v.matches.length)})).filter(p=>p.versions.length);
    const allPeople=analyze(people,eligible),allPlaces=analyze(places,eligible),pairedPlaces=new Map(places.map(e=>[e.id,{entity:e,...record()}]));
    for(const p of eligible)for(const v of p.versions){
      const byEntity=new Map();for(const m of v.matches){const e=wanted.get(m.entity);if(!e)continue;
        if(options.closeNames!==false&&e.kind==='person'&&m.quality==='cooccurrence')continue;
        if(!byEntity.has(m.entity))byEntity.set(m.entity,[]);byEntity.get(m.entity).push(m);
      }
      for(const person of people){const left=byEntity.get(person.id);if(!left)continue;
        const aggregate=new Set();let pageRank=99;
        for(const place of places){const right=byEntity.get(place.id);if(!right)continue;
          const matches=new Set();let rank=99;
          for(const a of left)for(const b of right){if(!options.includeOverlap&&a.offsets.some(([x,y])=>b.offsets.some(([s,e])=>x<e&&s<y)))continue;
            rank=Math.min(rank,Math.max(ranks[a.quality]??99,ranks[b.quality]??99));matches.add(a);matches.add(b);
          }
          if(!matches.size)continue;
          const row=cells.get(person.id);if(!row.has(place.id))row.set(place.id,record());add(row.get(place.id),p,v,[...matches],rank,1);
          add(pairedPlaces.get(place.id),p,v,[...matches],rank,1);
          pageRank=Math.min(pageRank,rank);matches.forEach(m=>aggregate.add(m));
        }
        if(aggregate.size)add(stats.get(person.id),p,v,[...aggregate],pageRank,1);
      }
    }
    // A page with any valid same-reading pair belongs to the paired group only.
    // A name in the original and a place only in the edited version do not form a pair.
    function withoutPairs(all,paired){return new Map([...all].map(([id,s])=>{
      const unmatched={entity:s.entity,...record()};
      for(const [key,p] of s.records)if(!paired.get(id).pageRanks.has(key))for(const v of p.versions.values()){
        const matches=[...v.matches];add(unmatched,p.page,v.version,matches,Math.min(...matches.map(m=>ranks[m.quality]??99)));
      }
      return [id,unmatched];
    }))}
    const unpairedPeople=withoutPairs(allPeople.stats,stats),unpairedPlaces=withoutPairs(allPlaces.stats,pairedPlaces);
    const unpairedPlaceTotal=analyze(places,[...unpairedPlaces.values()].flatMap(materialize)).total;
    return {cells,stats,columns:places.map(e=>e.id),allPeople:allPeople.stats,allPlaces:allPlaces.stats,unpairedPeople,unpairedPlaces,allPlaceTotal:allPlaces.total,unpairedPlaceTotal};
  }
  function combineRecords(records){
    const total=record();
    for(const source of records)if(source)for(const [key,p] of source.records)for(const v of p.versions.values())add(total,p.page,v.version,[...v.matches],source.pageRanks.get(key));
    return total;
  }
  function pageCombinations(entities,pages){
    const kinds=new Map(entities.map(e=>[e.id,e.kind])),combinations=new Map([1,2,4,3,5,6,7].map(mask=>[mask,record()])),distant=record(),total=record();
    const overlaps=(match,others)=>others.some(other=>match.offsets.some(([a,b])=>other.offsets.some(([x,y])=>a<y&&x<b)));
    for(const p of pages)for(const v of p.versions){
      const matches=v.matches.filter(m=>kinds.has(m.entity));
      const people=matches.filter(m=>kinds.get(m.entity)==='person'&&m.quality!=='cooccurrence');
      const places=matches.filter(m=>kinds.get(m.entity)==='place'&&!overlaps(m,people));
      const surnames=matches.filter(m=>kinds.get(m.entity)==='surname'&&!overlaps(m,[...people,...places]));
      const groups=[[1,people],[2,surnames],[4,places]].filter(([,items])=>items.length);
      const mask=groups.reduce((value,[bit])=>value|bit,0),evidence=groups.flatMap(([,items])=>items);
      if(mask){const rank=Math.max(...groups.map(([,items])=>Math.min(...items.map(m=>ranks[m.quality]??99))));add(combinations.get(mask),p,v,evidence,rank);add(total,p,v,evidence,rank)}
      else{const clues=matches.filter(m=>kinds.get(m.entity)==='person'&&m.quality==='cooccurrence');if(clues.length){add(distant,p,v,clues,4);add(total,p,v,clues,4)}}
    }
    return {combinations,distant,total};
  }
  function generalRows(result,exporter,exportedAt=new Date().toISOString()){
    const entities=result.catalog.entities,active=entities.filter(e=>e.enabled!==false),pages=result.pages;
    const data=analyze(entities,pages),cross=buildCross(active.filter(e=>e.kind!=='place'),active.filter(e=>e.kind==='place'),pages);
    const labels={person:'Nombre completo',surname:'Apellido / familia',place:'Lugar'};
    const header=['Referente','Tipo','Prioridad','Estado del criterio','Sinónimos explícitos','Páginas distintas','Documentos','Páginas literal o variante','Páginas solo proximidad o aproximación','Páginas solo pistas','Páginas nombre y apellido separados','Páginas con cruce persona/apellido y lugar','Páginas sin ese cruce (excluye nombres separados)','Puntaje heurístico','Páginas en original','Páginas en edición humana','Páginas en segunda lectura','Referencias de páginas','Origen del criterio','Revisión de criterios','Fecha del análisis (UTC)','Páginas recorridas','Páginas del inventario','Exportado por','Fecha de exportación (UTC)','Alcance'];
    return [header,...entities.map(e=>{
      const s=data.stats.get(e.id),n=count(s),records=materialize(s),inactive=e.enabled===false;
      const unpaired=(e.kind==='place'?cross.unpairedPlaces:cross.unpairedPeople).get(e.id);
      const all=(e.kind==='place'?cross.allPlaces:cross.allPeople).get(e.id);
      const singles=unpaired?.pageRanks.size||0,paired=(all?.pageRanks.size||0)-singles;
      const versions=predicate=>records.filter(p=>p.versions.some(v=>predicate(v.version))).length;
      return [e.label,labels[e.kind],e.priority,inactive?'Inactivo: no buscado':n.pages?'Con hallazgos':'Sin hallazgos',
        (e.patterns||[]).filter(p=>p.origin==='alias').map(p=>p.label).join(' | '),n.pages,n.documents,n.byGroup.strong,n.byGroup.review,n.byGroup.context,e.kind==='person'?n.distantPages:0,
        paired,singles,n.score,versions(v=>v==='original'),versions(v=>v==='human'),versions(v=>v.startsWith('second_reading:')),
        records.map(p=>p.document+' · p. '+p.page).join(' | '),(e.sources||[]).map(s=>s.sheet+' · fila '+s.row).join(' | ')||'Añadido en la app',
        result.catalog.revision,new Date(result.created*1000).toISOString(),result.coverage.searched_pages,result.coverage.inventory_pages,exporter,exportedAt,
        'Todos los criterios del análisis guardado; sin filtros de pantalla ni depuración humana. Las filas pueden compartir páginas. Los cruces requieren la misma lectura y palabras distintas.'];
    })];
  }
  function typedRanges(matches,entityKinds){
    const events=[];for(const m of matches){const kind=entityKinds.get(m.entity)||'surname';for(const [a,b] of m.offsets)if(b>a){events.push([a,kind,1],[b,kind,-1])}}
    events.sort((a,b)=>a[0]-b[0]);const counts={person:0,place:0,surname:0},ranges=[];let previous=events[0]?.[0]||0,index=0;
    while(index<events.length){const position=events[index][0],kind=['person','place','surname'].find(k=>counts[k]>0);
      if(position>previous&&kind){const last=ranges.at(-1);if(last&&last[1]===previous&&last[2]===kind)last[1]=position;else ranges.push([previous,position,kind]);}
      while(index<events.length&&events[index][0]===position){const [,k,delta]=events[index++];counts[k]+=delta;}previous=position;
    }return ranges;
  }
  return {ranks,scores,groups,group,pageKey,filterChoice,filterEntities,filterSource,filterEvidence,relevance,recordRelevance,count,materialize,audit,analyze,buildMatrix,buildCross,combineRecords,pageCombinations,generalRows,typedRanges};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=PriorityBalance;
