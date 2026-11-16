// Presentation-only navigation: no processing or review state changes.
const layoutLabels={es:['Resumen','Revisión','Cómo funciona','Progreso por carpeta','Cómo funciona','Actividad y recursos'],en:['Overview','Review','How it works','Progress by folder','How it works','Activity and resources'],fr:['Vue d’ensemble','Révision','Comment ça fonctionne','Progression par dossier','Fonctionnement','Activité et ressources']};
const overview=document.createElement('div'),reviewView=document.createElement('div'),technology=document.createElement('div');
overview.id='view-overview';reviewView.id='view-review';technology.id='view-technology';
const main=document.querySelector('main'),header=main.querySelector('header');
const originalChildren=[...main.children].filter(x=>x!==header);
main.append(overview,reviewView,technology);
const story=document.querySelector('.story'),explanation=document.querySelector('#como-funciona'),operations=document.querySelector('#operaciones');
const technical=document.createElement('details');technical.className='technical-details';technical.dataset.noI18n='';const summary=document.createElement('summary');technical.append(summary);overview.append(technical);
for(const el of originalChildren){
 if(el===story||el===explanation){technology.append(el);continue}
 if(el===work){reviewView.append(el);continue}
 if(el===operations||el.classList.contains('charts')){technical.append(el);continue}
 overview.insertBefore(el,technical);
}
overview.append(technology);
const technologyHeading=document.createElement('h2');technologyHeading.textContent='Cómo funciona';technology.prepend(technologyHeading);
// The issue inbox and page map live in the dedicated review workspace.
const nav=document.createElement('nav');nav.className='view-nav';nav.dataset.noI18n='';nav.setAttribute('aria-label','Dashboard');header.insertBefore(nav,header.querySelector('.language-control'));
const oldLink=header.querySelector('a[href="#como-funciona"]');if(oldLink)oldLink.remove();
// Keep utility controls together instead of wrapping the pause button on its own.
const headerTools=document.createElement('div');headerTools.className='header-tools';
headerTools.append(header.querySelector('.language-control'),header.querySelector('#pause'));header.append(headerTools);
let activeView='overview';
function showView(name){const explain=name==='technology';if(explain)name='overview';activeView=name;overview.hidden=name!=='overview';reviewView.hidden=name!=='review';technology.hidden=name!=='overview';drawNavigation();if(name==='overview')requestAnimationFrame(()=>render());if(explain)requestAnimationFrame(()=>technology.scrollIntoView({behavior:'smooth',block:'start'}));}
function drawNavigation(){const l=layoutLabels[uiLanguage];nav.innerHTML=['overview','review'].map((v,i)=>`<button aria-pressed="${v===activeView}" data-view="${v}">${l[i]}</button>`).join('');nav.querySelectorAll('button').forEach(b=>b.onclick=()=>showView(b.dataset.view));summary.textContent=l[5];}
const folderBars=document.createElement('div');folderBars.className='folder-bars';folderBars.dataset.noI18n='';overview.querySelector('#folders').closest('section').before(folderBars);
function drawFolders(){if(!state)return;folderBars.innerHTML=Object.entries(state.summary.folders).map(([name,g])=>`<div class="folder-progress"><div><strong>${esc(name)}</strong><span>${g.processed} / ${g.pages} PDF · ${Math.round(100*g.processed/Math.max(1,g.pages))}%</span></div><div class="track"><span class="bar" style="display:block;width:${100*g.processed/Math.max(1,g.pages)}%"></span></div></div>`).join('');}
const layoutRender=render;render=function(){layoutRender();drawFolders();drawNavigation()};
const style=document.createElement('style');style.textContent=`
[hidden]{display:none!important}.view-nav{display:flex;gap:4px}.view-nav button{border:0;background:transparent;border-radius:0;padding:12px}.view-nav button[aria-pressed=true]{border-bottom:2px solid var(--orange);font-weight:700}header{padding:12px 0 18px;gap:18px}header .brand img{width:46px;height:46px}header h1{font-size:23px}header>div>small{display:none}.brand .eyebrow{font-size:9px}.hero{grid-template-columns:1.4fr 1fr 1fr}.hero .value{font-size:34px}.cards{grid-template-columns:repeat(4,minmax(0,1fr))}.technical-details{margin:28px 0;border-top:1px solid var(--line);padding:20px 0}.technical-details>summary{cursor:pointer;font-weight:600}.folder-bars{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin:20px 0}.folder-progress{background:var(--white);border:1px solid var(--line);padding:20px}.folder-progress>div:first-child{display:flex;justify-content:space-between;gap:12px;margin-bottom:18px;font-size:12px}.folder-progress strong{overflow-wrap:anywhere}#view-review #review-work>h2:first-child{margin-top:12px}#view-technology .story{margin-top:20px}.review-split{grid-template-columns:3fr 2fr}.review-actions{position:sticky;bottom:0;background:var(--paper);padding:12px 0}.image-pane img{cursor:zoom-in}.image-pane img.zoomed{width:180%;max-width:none;cursor:zoom-out}.issue-row button{align-self:center;white-space:nowrap}@media(max-width:900px){.hero{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,1fr)}.review-split{grid-template-columns:1fr}.view-nav{order:3;width:100%}}@media(max-width:500px){.cards{grid-template-columns:1fr}}
/* Main navigation has its own row; these rules do not affect dialog headers. */
main>header{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"brand tools" "navigation navigation";gap:12px 24px;padding:12px 0 8px;margin-bottom:18px}
main>header>.brand{grid-area:brand;min-width:0}
main>header>.header-tools{grid-area:tools;display:flex;align-items:center;justify-content:flex-end;gap:16px;min-width:0}
main>header>.header-tools .language-control{display:flex;align-items:center;gap:8px}
main>header>.header-tools button{white-space:nowrap}
main>header>.view-nav{grid-area:navigation;min-width:0;width:100%;flex-wrap:wrap;gap:4px}
main>header>.view-nav button{white-space:nowrap}
@media(max-width:700px){main>header{grid-template-columns:minmax(0,1fr);grid-template-areas:"brand" "tools" "navigation";gap:12px}main>header>.header-tools{justify-content:space-between;flex-wrap:wrap;gap:8px}main>header>.header-tools .language-control{flex-wrap:wrap}main>header>.view-nav button{font-size:12px;padding:10px 8px}}
`;document.head.append(style);
modal.addEventListener('click',e=>{if(e.target.matches('.image-pane img'))e.target.classList.toggle('zoomed')});
drawFolders();showView('overview');
