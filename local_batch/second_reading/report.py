"""Metadata-only report; no confidential transcription is printed."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'results/second_reading/pilot_01'
def report():
 manifest=json.loads((ROOT/'manifest.json').read_text());summary=json.loads((ROOT/'summary.json').read_text());rows=summary['results'];resources=[]
 for line in (ROOT/'telemetry.jsonl').read_text().splitlines():
  try:resources.append(json.loads(line))
  except ValueError:pass
 metrics=dict(status=summary['status'],pages=len(rows),without_automatic_flags=sum(not r['flags'] for r in rows),with_automatic_flags=sum(bool(r['flags']) for r in rows),inference_seconds=sum(r['inference_seconds'] for r in rows),baseline_seconds=sum(r['baseline_seconds'] for r in rows),load_seconds=manifest.get('load_seconds'),baseline_integrity_verified=manifest.get('baseline_integrity_verified',False),accuracy_evaluated=False)
 if resources:metrics['resources']=dict(vram_used_peak_mib=max(r['vram_used_mib'] for r in resources),vram_free_min_mib=min(r['vram_free_mib'] for r in resources),ram_available_min_gib=min(r['ram_available_gib'] for r in resources),gpu_temperature_max_c=max(r['temperature_c'] for r in resources))
 (ROOT/'metrics.json').write_text(json.dumps(metrics,indent=2))
 lines=['# Piloto de segunda lectura local · 27B','','Estado: '+summary['status']+'.','','Tres páginas seleccionadas por alertas del procesamiento masivo. No es una muestra aleatoria ni una medición de exactitud. El prompt cambió, por lo que no se aísla el efecto del tamaño del modelo. Se mantuvieron imagen, presupuesto de salida y temperatura. No se utilizó Astra ni se envió contenido fuera del equipo.','','| Documento | Página PDF | Avisos 9B | Avisos 27B | Segundos 9B → 27B |','|---|---:|---|---|---:|']
 for r in rows:lines.append('| '+r['document']+' | '+str(r['page'])+' | '+', '.join(r['baseline_flags'])+' | '+(', '.join(r['flags']) or 'Ninguno detectado')+' | '+f"{r['baseline_seconds']:.1f} → {r['inference_seconds']:.1f}"+' |')
 lines+=['','## Interpretación','','La desaparición de repetición o truncamiento es una señal operativa, no prueba de transcripción correcta. Las tres lecturas deben compararse con la imagen por una persona. Los archivos originales y las correcciones humanas se conservan; no se aceptó automáticamente ninguna respuesta.','','## Recursos y tiempos','', '```json',json.dumps(metrics,ensure_ascii=False,indent=2),'```','','## Artefactos','','Cada case_XX contiene transcription.md, response.json, metadata.json y comparison.diff. El tablero ofrece una comparación de sólo lectura en el menú secundario de las páginas del piloto. No se reprocesan las otras doce páginas hasta evaluar si aporta una mejora.']
 (ROOT/'INFORME.md').write_text('\n'.join(lines)+'\n');print(json.dumps(metrics,ensure_ascii=False))
if __name__=='__main__':report()
