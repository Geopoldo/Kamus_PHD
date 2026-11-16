const fs=require('fs'),vm=require('vm'),assert=require('assert');
const c=vm.createContext({localStorage:{getItem:()=>null}});vm.runInContext(fs.readFileSync(__dirname+'/i18n.js','utf8'),c);
function translate(lang,text){c.input=text;vm.runInContext(`uiLanguage='${lang}'`,c);return vm.runInContext('translateText(input)',c)}
assert.equal(translate('fr','Tiempo para terminar TODO el lote'),'Temps pour terminer TOUT le lot');
assert.equal(translate('en','Documentos pendientes'),'Remaining documents');
assert.equal(translate('fr','20 filas'),'20 lignes');
assert.equal(translate('es','Tiempo para terminar TODO el lote'),'Tiempo para terminar TODO el lote');
assert.equal(translate('en','Nous préparons une image à lire.'),'Nous préparons une image à lire.');
assert.equal(translate('fr','Organizamos el archivo.'),'Nous organisons les archives.');
console.log('6 translation checks passed');
