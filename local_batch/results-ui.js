// Results mount and navigation. The unified editor owns this workspace.
const resultsView=document.createElement('div');resultsView.id='view-results';resultsView.dataset.noI18n='';main.append(resultsView);resultsView.hidden=true;
let resultDoc='',resultPage=1;
const baseNavigation=drawNavigation;drawNavigation=function(){baseNavigation();const b=document.createElement('button');b.textContent=({es:'Banco de transcripciones',en:'Transcript library',fr:'Bibliothèque des transcriptions'})[uiLanguage];b.dataset.view='results';b.setAttribute('aria-pressed',String(activeView==='results'));b.onclick=()=>showView('results');nav.insertBefore(b,nav.children[1]||null)};
function renderResults(){}
drawNavigation();
