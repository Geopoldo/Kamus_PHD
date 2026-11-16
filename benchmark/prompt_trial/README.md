# Piloto de instrucciones locales

Implementación de `../PLAN_PRUEBA_PROMPTS_LOCALES.md`. Los prompts se extrajeron literalmente del plan.

## Uso

Desde la raíz del proyecto:

```bash
python3 -m unittest discover -s benchmark/prompt_trial/tests -v
python3 benchmark/prompt_trial/run.py
python3 benchmark/prompt_trial/run.py --execute --run-id IDENTIFICADOR_NUEVO
```

El primer comando prueba componentes en CPU; el segundo valida rutas sin cargar modelos. El tercero ejecuta seis inferencias secuenciales. `--repeat-baseline` ejecuta también el control original, con doce intentos totales. El acceso GPU puede requerir ejecución fuera del sandbox. Una ejecución existente no se sobrescribe; la reanudación automática se rechaza deliberadamente.

El servidor utiliza el binario llama.cpp existente, una petición por vez y las reservas de RAM/VRAM del plan. Se registran huellas, comandos, respuestas crudas, segmentos parseados y telemetría. El monitor vigila desde la carga y detiene el proceso propio si falla la telemetría o se cruzan los umbrales.

## Revisión y evaluación

```bash
python3 benchmark/prompt_trial/review.py prepare --text RUTA_SALIDA.txt --output asignaciones.json
python3 benchmark/prompt_trial/review.py score --text RUTA_SALIDA.txt --assignments asignaciones.json --output metricas.json
```

`prepare` crea una partición exhaustiva con offsets Unicode y candidatos de referencia. El archivo necesita revisión explícita: fijar `page_ids`, agrupar spans por pasaje, vincular unidades de referencia y marcar omitidos/extras/formato. `score` rechaza spans reutilizados, texto sin asignar, referencia clara ausente y asignaciones pendientes. No convierte automáticamente coincidencias favorables en correspondencias verificadas.

Los resultados históricos se revisan con el mismo procedimiento. El baseline no recibe etiquetas retrospectivas; las asignaciones documentales y el cumplimiento de etiquetas son dos conceptos distintos. Una lectura marcada UNCLEAR se puntúa normalmente; ILLEGIBLE se conserva como abstención y no reduce la referencia.

## Estado y límites

El ejecutor, parser, métricas y revisión explícita están implementados. La asignación visual de regiones y la tabla pareada final requieren los archivos de revisión: no hay aún un alineador automático adjudicado, una evaluación de entidades localizadas ni un informe completo de estructura. No presentar el WER exploratorio anterior como resultado de este piloto. CER se identifica como texto físico con espacios normalizados; las reconstrucciones verificadas se usan para WER. No se declara CER de palabras reconstruidas para evitar ocultar guiones o saltos sin revisar.

Los modelos pueden exceder el presupuesto real de contexto a pesar de los máximos configurados: se conserva el error o truncamiento y no se amplían límites automáticamente. La condición de finalización `stop` se registra por separado de los errores del parser.

Para generar el resumen de ejecución y los paquetes de revisión:

```bash
python3 benchmark/prompt_trial/report.py benchmark/experiments/prompt_pilot_v1/IDENTIFICADOR
```

Este informe muestra estados, tiempos y reservas observadas; no inventa métricas sobre regiones pendientes. Los archivos de asignación existentes nunca se sobrescriben al regenerarlo.
