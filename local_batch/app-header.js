// Shared product identity and a factual explanation of local inference.
(()=>{
 const h=main.querySelector('header'),brand=h?.querySelector('.brand');if(!brand)return;
 h.classList.add('app-header');
 const title=brand.querySelector('h1');
 const titleRow=document.createElement('div');titleRow.className='app-title-row';title.before(titleRow);titleRow.append(title);
 const badge=document.createElement('details');badge.className='app-local-badge';badge.dataset.noI18n='';
 const summary=document.createElement('summary'),dot=document.createElement('span'),label=document.createElement('span'),description=document.createElement('p');
 dot.className='app-local-dot';dot.setAttribute('aria-hidden','true');summary.append(dot,label);badge.append(summary,description);titleRow.append(badge);
 const utilities=document.createElement('div');utilities.className='app-header-utilities';
 for(const control of [h.querySelector('.language-control'),h.querySelector('#pause')])if(control)utilities.append(control);
 const oldTools=h.querySelector('.header-tools');if(oldTools&&!oldTools.children.length)oldTools.remove();
 h.append(utilities);
 function paint(){const messages={es:['Procesamiento local · datos bajo tu control','La transcripción y el análisis se ejecutan con modelos locales. Tus documentos no se envían a servicios externos de inteligencia artificial.'],en:['Local processing · your data, your control','Transcription and analysis run on local models. Your documents are not sent to external AI services.'],fr:['Traitement local · vos données sous votre contrôle','La transcription et l’analyse utilisent des modèles locaux. Vos documents ne sont pas envoyés à des services externes d’intelligence artificielle.']}[uiLanguage]||[];label.textContent=messages[0];description.textContent=messages[1]}
 const prior=setLanguage;setLanguage=function(language){prior(language);paint()};paint();
 const css=document.createElement('style');css.textContent=`
main>header.app-header{display:flex!important;align-items:center!important;justify-content:space-between!important;gap:20px 30px!important;flex-wrap:wrap!important;padding:20px 0 0!important;margin-bottom:20px!important}
main>header.app-header>div:first-child{flex:1 1 580px;min-width:0}main>header.app-header>div:first-child>small{display:none}
main>header.app-header .brand{display:flex!important;align-items:center!important;gap:20px!important;min-width:0}main>header.app-header .brand>img{width:72px!important;height:80px!important;max-width:none!important;flex:0 0 72px;object-fit:contain}main>header.app-header .brand>div{min-width:0;flex:1}
main>header.app-header .brand .eyebrow{font-size:10px!important;letter-spacing:1.5px!important;line-height:1.6;margin-bottom:5px}
main>header.app-header .brand h1{font-size:clamp(23px,1.7vw,29px)!important;letter-spacing:-1px!important;line-height:1.2!important;margin:0!important;font-weight:550!important;white-space:normal!important}
.app-title-row{display:flex;align-items:center;gap:12px 22px;flex-wrap:wrap}.app-local-badge{position:relative;font-size:11px;color:#315e4d;margin:0}.app-local-badge>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;padding:7px 10px;background:#edf3e9;border:1px solid #d7e2d2;border-radius:30px;white-space:normal;line-height:1.4}.app-local-badge>summary::-webkit-details-marker{display:none}.app-local-dot{height:7px;width:7px;flex:0 0 7px;border-radius:50%;background:#23765c;box-shadow:0 0 0 3px #dbeadd}.app-local-badge>p{position:absolute;top:100%;left:0;z-index:95;width:320px;max-width:75vw;padding:16px;background:#fffefa;border:1px solid #d7e2d2;box-shadow:0 10px 30px #23382a22;border-radius:10px;font-size:13px;line-height:1.8;color:#3c5d4c}
main>header.app-header>.app-header-utilities{flex:0 1 auto;display:flex;align-items:center;justify-content:flex-end;gap:12px}.app-header-utilities .language-control{display:flex;align-items:center;gap:10px;font-size:10px}.app-header-utilities select{border-radius:8px;padding:10px 13px;min-height:39px}.app-header-utilities #pause{font-size:11px;border-radius:8px;padding:10px 12px;background:transparent}
main>header.app-header>nav{order:5;flex:1 0 100%;margin:0!important;padding:10px 0 0!important;border-top:1px solid #dde1d8;display:flex!important;gap:6px;overflow-x:auto;scrollbar-width:thin;white-space:nowrap;flex-wrap:nowrap!important}main>header.app-header>nav button{font-size:13px;padding:13px 14px;border-radius:0;flex-shrink:0}main>header.app-header>a{display:none}
@media(max-width:900px){main>header.app-header{padding-top:12px!important;gap:12px!important}main>header.app-header>div:first-child{flex-basis:100%}.app-title-row{gap:8px 15px}main>header.app-header>.app-header-utilities{width:100%;justify-content:flex-end}main>header.app-header .brand>img{width:60px!important;height:68px!important;flex-basis:60px}}
@media(max-width:550px){main>header.app-header .brand{gap:13px!important}main>header.app-header .brand>img{width:52px!important;height:65px!important;flex-basis:52px}main>header.app-header .brand h1{font-size:22px!important}.app-header-utilities .language-control{font-size:0}.app-header-utilities .language-control select{font-size:12px}.app-local-badge{font-size:10px}main>header.app-header>nav button{font-size:12px;padding:12px 10px}}
`;document.head.append(css);
})();
