"""Summarize execution without fabricating unreviewed recognition metrics."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);args=ap.parse_args();r=args.run
 rows=[]
 for p in sorted((r/'metadata').glob('*/*/*.json')):
  a=json.loads(p.read_text());model=a['model'];sample=a['sample'];variant=a['variant'];new=r/'raw'/variant/model/(sample+'.txt')
  pid={'typed':'typed_letter_1914.p01','handwritten':'handwritten_letter_1865.p01','pdf_page_02':'british_system_notes.p02'}[sample]
  for v in ['baseline_original',variant]:
   old=ROOT.parent/('extended_results' if sample.startswith('pdf') else 'results')/model/(sample+'.txt')
   text=old if v=='baseline_original' else new
   out=r/'assignments'/v/model/(sample+'.json')
   if text.exists() and not out.exists():
    subprocess.run([sys.executable,str(ROOT/'review.py'),'prepare','--text',str(text),'--output',str(out)],check=True)
    packet=json.loads(out.read_text());packet['page_ids']=[pid];packet['reference_candidates']=[u for u in packet['reference_candidates'] if u['page_id']==pid];out.write_text(json.dumps(packet,indent=2,ensure_ascii=False)+'\n')
  oldmeta=ROOT.parent/('extended_results' if sample.startswith('pdf') else 'results')/model/(sample+'.json')
  historical=json.loads(oldmeta.read_text());a['historical_seconds']=historical.get('seconds');rows.append(a)
 resources=[json.loads(x) for x in (r/'resource_monitor.jsonl').read_text().splitlines()]
 md=['# Piloto de instrucciones: ejecución y estado de evaluación','','Se ejecutó el prompt literal_regions_v1 contra las tres imágenes originales, uno por uno. Los tiempos de control proceden de ejecuciones históricas; no implican un ensayo de rendimiento contemporáneo.','','| Modelo | Página | Estado | Tiempo nuevo (s) | Histórico (s) | Errores de parser |','|---|---|---|---:|---:|---:|']
 for a in rows:md.append(f"| {a['model']} | {a['sample']} | {a['status']} | {a.get('seconds',0):.2f} | {a.get('historical_seconds',0):.2f} | {len(a.get('parser_errors',[]))} |")
 md+=['','## Recursos','']
 for model in sorted({x['model'] for x in resources}):
  rs=[x for x in resources if x['model']==model];md.append(f"- {model}: mínimo observado {min(x['vram_free_mib'] for x in rs)} MiB VRAM libre y {min(x['ram_available_gib'] for x in rs):.2f} GiB RAM disponible.")
 md+=['','## Evaluación pendiente de adjudicación','','Las carpetas assignments contienen las salidas originales y nuevas con offsets y unidades candidatas de Astra. Están marcadas needs_review. El evaluador rechaza puntuarlas como si ya estuvieran verificadas. Falta revisar correspondencias por regiones, exclusiones de dudas y estados de tachados antes de emitir WER/CER pareados. La validez de etiquetas no implica lectura correcta.','','Referencia y salidas históricas se conservaron. No se eligió un ganador a partir de estos datos sin adjudicar.']
 (r/'report.md').write_text('\n'.join(md)+'\n');(r/'results.json').write_text(json.dumps(dict(execution=rows,evaluation_status='needs_region_review'),indent=2)+'\n')
 print('\n'.join(md))
if __name__=='__main__':main()
