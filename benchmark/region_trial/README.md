# Prueba exploratoria por regiones

`prepare.py` genera 45 recortes a resolución original de regiones cuyos segmentos Astra son todos claros y activos. La selección se realiza antes de inferencia. El archivo `config.json` sólo entrega rutas de imágenes al modelo; `reference.json` conserva texto y huellas para evaluar.

`score.py RUTA_EJECUCION` compara toda la salida de cada recorte, sin anclas textuales. Una salida ausente cuenta como omisión completa; no confundir muestras no ejecutadas con resultados de calidad del modelo. Sólo utilizar agregados cuando todas las inferencias estén completas.

Ejecución exploratoria: `../experiments/prompt_pilot_v1/regions-20261114-v1`. Detenida anticipadamente: un recorte llegó a 4096 tokens y terminó por límite. No hay comparación global válida. Los recortes usan cajas aproximadas de Astra, no límites de texto verificados visualmente: pueden cortar trazos o incluir regiones vecinas.

Siguiente paso: revisar visualmente las cajas, agregar márgenes de contexto, limitar la salida, y ejecutar primero tres recortes (directorio, cuerpo manuscrito, margen). Incluir regiones difíciles requiere máscaras explícitas para dudas y tachados. Esta selección clara excluye gran parte del cuerpo manuscrito y no mide rendimiento integral.

La comparación causal con página completa requiere asignar las salidas completas a estas mismas regiones; no comparar el WER de este ensayo directamente con el informe histórico de pasajes seleccionados.

La referencia Astra permanece congelada. El ejecutor conserva exclusión mutua GPU, telemetría y reservas de memoria. Ahora respeta `variant` en el archivo de configuración.
