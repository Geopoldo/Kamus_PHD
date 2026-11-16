# Guía para conectarte al servicio de transcripción de tu hermano

> **Configuración actual:** servicio sin clave en `http://192.168.1.14:8090`, autorizado temporalmente para cualquier equipo del rango de intranet **192.168.1.0/24**. La aplicación rechaza solicitudes de otras redes. Más adelante el propietario podrá restringirlo a la IP concreta del hermano.

## 1. Dirección y funcionamiento

El servicio está en el portátil **ewok-Legion-Pro-7-16IAX10H**, con GPU RTX 5080 Laptop. Tu equipo envía documentos; el portátil hace la inferencia y guarda los resultados para descargarlos después.

| Dato | Valor |
|---|---|
| IP actual del servidor en la intranet | **192.168.1.14** |
| Puerto TCP | **8090** |
| Dirección base | **http://192.168.1.14:8090** |
| Comprobación del servicio | `GET /health`, sin clave |
| Modelo | Qwen3.5-9B, cuantización Q4_K_M |
| Procesamiento | Una página por vez, con el prompt original de transcripción |
| Entrega | JSON y Markdown |
| Autenticación | Sin clave, acceso por intranet |

Ambos equipos están en la misma intranet: **no necesitas Tailscale, VPN, redirección de puertos del router ni acceso a Internet para llamar a la API**. La instalación inicial de Python puede requerir Internet.

La IP se obtuvo de la interfaz Wi-Fi activa `wlp130s0f0`, con red `192.168.1.0/24` y puerta de enlace `192.168.1.1`. Las direcciones `172.17.x.x`, `172.18.x.x`, etc. que puedan aparecer en el servidor son redes de contenedores y no son la dirección que debes usar.

**La IP se asigna por DHCP y puede cambiar.** Si deja de responder después de reiniciar o cambiar de red, confirmar la nueva IP con el propietario. Conviene reservar `192.168.1.14` para este portátil desde el router, si el administrador de la red puede hacerlo.

## 2. Qué debes recibir antes de empezar

Pide al propietario:

1. Confirmación de que el portátil está encendido, despierto y con el servicio activo.
2. Los archivos `client.py` y `batch_client.py`, situados en la carpeta `inference_service` del proyecto del servidor. Puedes recibirlos junto a esta guía en `PAQUETE_CLIENTE_INTRANET.zip`.

No necesitas copiar modelos, pesos, la base de datos ni la carpeta `data`. No necesitas una GPU especial. Para utilizar el cliente basta Python 3; no requiere instalar paquetes con pip.

Por decisión del propietario, **el servicio no pide clave**. Cualquier equipo del rango permitido `192.168.1.0/24` que pueda alcanzar `192.168.1.14:8090` puede enviar solicitudes y consultar resultados si conoce sus identificadores. No hay cuentas ni aislamiento entre usuarios; usarlo sólo en la intranet de confianza.

## 3. Comprobar la conexión en Windows

Abre **PowerShell**:

```powershell
Test-NetConnection 192.168.1.14 -Port 8090
```

Busca `TcpTestSucceeded : True`. Esto confirma acceso al puerto, pero no la disponibilidad de la GPU.

Configura la dirección para esta ventana y comprueba el servicio:

```powershell
$env:OCR_API_URL = 'http://192.168.1.14:8090'
Invoke-RestMethod -Uri "$env:OCR_API_URL/health"
```

La respuesta debe contener `status: ok` y `gpu_concurrency: 1`. No necesitas clave ni cabeceras de autenticación. Puedes abrir `http://192.168.1.14:8090/health` en el navegador para comprobarlo; no hay una interfaz web para subir archivos.

## 4. Comprobar la conexión en Linux o macOS

Abre una terminal y configura estas variables:

```bash
export OCR_API_URL='http://192.168.1.14:8090'
curl --fail-with-body "$OCR_API_URL/health"
```

Los comandos de terminal de esta guía son para **Bash**; en macOS puedes ejecutar `bash` primero.

Respuesta esperada:

```json
{"status": "ok", "gpu_concurrency": 1}
```

La API utiliza HTTP dentro de la intranet; el tráfico no tiene cifrado HTTPS propio. Usarla únicamente en esta red de confianza. No abrir el puerto hacia Internet. Si cambia el escenario de red, habrá que configurar cifrado o una conexión privada.

## 5. Enviar un documento con el cliente Python

Guarda `client.py` en una carpeta de tu equipo. Abre una terminal en esa carpeta y configura las variables del apartado anterior.

### Windows / PowerShell

Comprueba que tienes Python:

```powershell
py -3 --version
```

Envía un archivo, ajustando su ruta:

```powershell
py -3 .\client.py 'C:\Documentos\carta.pdf' --output '.\carta_resultado.json'
```

Si tu instalación utiliza `python` en lugar de `py`, usa `python` en esos comandos. Si ninguno existe, instala Python 3 desde [python.org](https://www.python.org/downloads/) y vuelve a abrir la terminal.

### Linux / macOS

```bash
python3 --version
python3 ./client.py '/ruta/documentos/carta.pdf' --output './carta_resultado.json'
```

El cliente sube el archivo y muestra algo parecido a:

```text
Job: IDENTIFICADOR_DEL_TRABAJO
queued
processing
complete
carta_resultado.json
```

**Guarda el identificador.** El cliente consulta el estado cada cinco segundos y descarga JSON cuando el trabajo termina como `complete` o `partial`. Usa un nombre de salida distinto para cada documento: un archivo de salida existente puede sobrescribirse. La carpeta de destino debe existir.

Si cierras el cliente después de terminar la subida, el servidor puede seguir trabajando. Puedes recuperar el resultado con el identificador. **Ejecutar otra vez `client.py` vuelve a subir el documento y crea otro trabajo**; no reanuda el anterior ni elimina duplicados.

## 5A. Procesar varios archivos con la cola y descargar todos los resultados

El servidor **ya tiene una cola persistente**: recibe documentos, los guarda y procesa uno por turno. Las páginas de cada documento se procesan secuencialmente. Enviar varios archivos no ejecuta varios modelos a la vez.

Para un lote usa **`batch_client.py`**. Este programa envía archivos, consulta los trabajos y descarga un JSON y un Markdown por documento. No requiere paquetes de pip. Configura antes `OCR_API_URL` como en los apartados 3 o 4.

### Windows / PowerShell: una carpeta completa

Guarda `batch_client.py` en la carpeta donde abres PowerShell:

```powershell
py -3 .\batch_client.py --folder 'C:\Documentos\Escaneados' --output-dir '.\resultados_lote_01'
```

También puedes elegir archivos concretos:

```powershell
py -3 .\batch_client.py 'C:\Documentos\carta.pdf' 'C:\Documentos\otra.png' --output-dir '.\resultados_lote_01'
```

### Linux / macOS

```bash
python3 ./batch_client.py --folder '/ruta/escaneados' --output-dir './resultados_lote_01'
```

O elegir archivos:

```bash
python3 ./batch_client.py '/ruta/carta.pdf' '/ruta/otra.png' --output-dir './resultados_lote_01'
```

`--folder` incluye PDF, PNG, JPG y JPEG directamente dentro de esa carpeta; no recorre subcarpetas. No mezclar la carpeta de entrada con la de resultados. No ejecutar dos clientes por lotes simultáneamente sobre la misma carpeta de salida.

### Qué se guarda

La carpeta de resultados tendrá nombres similares a:

```text
resultados_lote_01/
  batch_manifest.json
  carta-IDENTIFICADOR.json
  carta-IDENTIFICADOR.md
  otra-OTRO_IDENTIFICADOR.json
  otra-OTRO_IDENTIFICADOR.md
```

`batch_manifest.json` registra archivos, huellas, identificadores y estados. **No lo borres mientras quieras retomar ese lote.** Los identificadores en los nombres evitan que dos documentos con el mismo nombre se sobrescriban.

El cliente mantiene hasta 20 trabajos propios pendientes/activos y envía los restantes cuando hay espacio. Si la cola del servidor está llena, espera y vuelve a comprobar. Conserva abierto el cliente hasta que todos los archivos se hayan enviado: los que siguen como `pending` en el manifiesto aún están sólo en tu equipo.

### Retomar después de cerrar el cliente o perder la conexión

Vuelve a configurar las variables si abriste otra terminal. Después ejecuta el cliente **con la misma carpeta de salida**:

PowerShell:

```powershell
py -3 .\batch_client.py --output-dir '.\resultados_lote_01'
```

Bash:

```bash
python3 ./batch_client.py --output-dir './resultados_lote_01'
```

El programa retoma los trabajos registrados; no vuelve a subir los que ya tienen identificador ni los que figuran como descargados. Si añades documentos nuevos a la carpeta de entrada, repite `--folder` con la misma carpeta de salida. Un archivo que cambió de contenido se trata como otro documento. Cambiar la ruta de entrada o borrar el manifiesto también puede causar un nuevo envío.

### Estados adicionales del cliente por lotes

| Estado en el manifiesto | Significado |
|---|---|
| `pending` | Archivo aún no enviado; necesita que el cliente siga funcionando. |
| `queued` / `processing` | Ya está registrado en el servidor; puede seguir aunque cierres el cliente. |
| `downloaded` | JSON y Markdown descargados. Revisar `server_status`: puede ser `complete` o `partial`. |
| `failed` | El servidor informó un fallo. No se reintenta automáticamente. |
| `submission_uncertain` | Se intentó subir, pero no se confirmó el identificador. Consultar al propietario antes de reenviar. |

Si se corta la conexión justo al subir, el servidor puede haber recibido el documento aunque el cliente no haya recibido su identificador. Para evitar duplicados, el cliente **no vuelve a enviar automáticamente** ese caso. El propietario debe comprobar la cola/base de datos y resolverlo contigo; no hay todavía un endpoint para listar todos los trabajos ni deduplicación del lado servidor.

Los archivos enviados continúan en cola cuando tu cliente se desconecta. Si el portátil servidor se apaga, no procesa ni recibe archivos; los trabajos en cola persisten y continúan cuando el propietario vuelva a iniciar el servicio. El que estaba en ejecución durante un reinicio puede quedar `failed` y debe reenviarse de forma coordinada.

El resumen `downloaded` cuenta descargas, no documentos revisados ni transcripciones perfectas. Comprueba `server_status` y los estados de las páginas antes de dar el lote por válido.

## 6. Usar directamente la API en PowerShell

Este método no necesita `client.py`. Primero configura la variable `OCR_API_URL` del apartado 3.

### Subir un PDF o una imagen

```powershell
$job = Invoke-RestMethod -Method Post `
  -Uri "$env:OCR_API_URL/v1/jobs" `
  -ContentType 'application/octet-stream' `
  -InFile 'C:\Documentos\carta.pdf'

$jobId = $job.job_id
$job
```

La respuesta contiene `job_id` y `status: queued`. El servidor responde HTTP `202 Accepted`; todavía no significa que haya terminado.

### Consultar el trabajo

```powershell
Invoke-RestMethod -Uri "$env:OCR_API_URL/v1/jobs/$jobId"
```

Si abriste otra ventana, vuelve a configurar `OCR_API_URL` y `$jobId` con el identificador guardado.

### Descargar resultados

Cuando el estado sea `complete` o `partial`:

```powershell
Invoke-WebRequest -Uri "$env:OCR_API_URL/v1/jobs/$jobId/result" `
  -OutFile '.\resultado.json'

Invoke-WebRequest -Uri "$env:OCR_API_URL/v1/jobs/$jobId/markdown" `
  -OutFile '.\resultado.md'
```

## 7. Usar directamente la API con curl

Configura antes las variables de Bash del apartado 4.

### Subir

```bash
curl --fail-with-body \
  -H 'Content-Type: application/octet-stream' \
  --data-binary '@/ruta/documentos/carta.pdf' \
  "$OCR_API_URL/v1/jobs"
```

**Enviar el archivo como cuerpo binario directo. No usar `curl -F`, formulario multipart ni JSON con una ruta de archivo.** El servidor no puede leer rutas de tu equipo.

Copia el identificador recibido:

```bash
JOB_ID='PEGA_AQUI_EL_JOB_ID'
curl --fail-with-body \
  "$OCR_API_URL/v1/jobs/$JOB_ID"
```

### Descargar

```bash
curl --fail-with-body \
  "$OCR_API_URL/v1/jobs/$JOB_ID/result" -o resultado.json

curl --fail-with-body \
  "$OCR_API_URL/v1/jobs/$JOB_ID/markdown" -o resultado.md
```

Estos comandos son para Bash. En Windows usar preferiblemente los ejemplos de PowerShell; `curl` puede ser un alias con comportamiento diferente según la versión.

## 8. Estados y lectura de los resultados

| Estado | Significado / acción |
|---|---|
| `queued` | Archivo recibido; esperando turno. No reenviar. |
| `processing` | Se está preparando o procesando el documento. Esperar. |
| `complete` | Todas las páginas terminaron técnicamente. Descargar y revisar. |
| `partial` | Hay páginas incompletas o fallidas; descargar lo disponible y revisar los estados por página. |
| `failed` | Falló el trabajo. Consultar `error` y avisar al propietario. |

No hay todavía porcentaje de progreso, posición en cola ni estimación fiable del tiempo restante.

Ejemplo **ilustrativo** del JSON descargado:

```json
{
  "job_id": "IDENTIFICADOR",
  "model": "qwen3.5-9b",
  "pages": [
    {
      "page": "page_001",
      "text": "Texto transcrito de la imagen...",
      "status": "complete",
      "finish_reason": "stop",
      "review_status": "unreviewed"
    }
  ]
}
```

`complete` y `finish_reason: stop` describen cómo acabó la ejecución, **no certifican la fidelidad de la transcripción**. Todos los resultados se entregan sin revisión humana (`unreviewed`). Revisar especialmente nombres propios, años, cifras, abreviaturas y texto tachado. Markdown facilita leer el texto; JSON conserva además estados por página.

Esta versión transcribe el texto visible. No ejecuta búsqueda contra el Excel de prioridades, ni entrega extracción validada de nombres, coordenadas o porcentajes de confianza.

## 9. Límites de esta versión

| Límite | Valor / comportamiento |
|---|---|
| Tamaño de subida | Hasta 30 MiB por archivo |
| PDF | Hasta 50 páginas; dividir documentos más largos antes de subir |
| Imagen individual | Hasta 25 millones de píxeles |
| Formatos recomendados | PDF, PNG y JPEG |
| TIFF multipágina / imágenes animadas | No usar para lotes: sólo se procesa el fotograma/página inicial |
| Cola | Máximo configurado de 20 trabajos pendientes o activos; evitar envíos masivos simultáneos |
| GPU | Una inferencia simultánea; no aumenta por enviar más trabajos |
| Tiempo | Depende del documento y de la cola; no hay compromiso de respuesta inmediata |
| Documentos largos | Hay un límite operativo cercano a una hora; no es una garantía de finalización |
| PDF escaneado | Se renderiza con un máximo de 2200 píxeles en el lado mayor |

Envía primero un documento corto. Si necesitas mejor lectura de letra muy pequeña, coordina una prueba con el propietario; no asumir que aumentar resolución o recortar siempre mejora el reconocimiento.

Los archivos originales y resultados se almacenan en el portátil del propietario. No hay borrado automático ni separación de cuentas; coordinar conservación y eliminación con él. Esta versión no consulta proveedores externos de inferencia.

## Tiempos de espera: qué hemos medido y cuánto conviene esperar

### Mediciones reales de este equipo

Las pruebas usaron Qwen3.5-9B Q4_K_M y páginas completas de los ejemplos. No son un ensayo de carga multiusuario ni una garantía para cualquier documento.

| Prueba | Tiempo observado | Qué incluye |
|---|---:|---|
| Una carta manuscrita, ensayo original | 6,76 s | Sólo inferencia, sin cargar el modelo |
| Una carta mecanografiada con más texto | 18,63 s | Sólo inferencia |
| Páginas del PDF de ejemplo | 3,41–8,14 s por página | Sólo inferencia; incluye una página casi vacía |
| Diez páginas de ejemplos, en total | 75,56 s, unos 1 min 16 s | Suma de inferencias; excluye carga, subida, renderizado y espera |
| Carga del modelo en los ensayos consultados | Aproximadamente 2–7 s por carga | Preparar el motor, sin inferencia |
| Una imagen enviada mediante la API | 6,39 s de inferencia + 2,01 s de carga | No es una medición completa desde el equipo remoto |

Las diez páginas promediaron unos 7,6 s de inferencia por página, pero la muestra es pequeña, tiene sólo tres documentos distintos y contiene una página casi vacía. No usar ese promedio como promesa de velocidad para un archivo histórico completo.

**La API actual carga el modelo una vez por documento y lo descarga después.** Un PDF de diez páginas paga una carga; diez imágenes enviadas como diez archivos pagan diez cargas. Además hay preparación, comprobación de archivos y pesos, conversión del PDF, escrituras y consultas del cliente. El coste de esas comprobaciones puede variar con la caché del disco. La API entrega el resultado del documento cuando acaba su procesamiento; no transmite páginas según van terminando.

### Márgenes orientativos para organizar el trabajo

La siguiente tabla es una **estimación de planificación con margen**, no tiempos medidos de lotes completos, percentiles ni un plazo de entrega. Supone cola inicialmente vacía, archivos similares a los ejemplos, GPU disponible y buena conexión de intranet.

| Envío | Ventana orientativa que conviene reservar |
|---|---:|
| Una imagen o PDF de una página | 15–60 segundos |
| Un PDF de unas diez páginas | 2–5 minutos |
| Diez imágenes como archivos separados | 3–10 minutos |
| Un PDF de cincuenta páginas, límite por archivo | 10–20 minutos; extrapolación no validada con un PDF de ese tamaño |
| Cien imágenes enviadas con batch | 20–60 minutos; extrapolación no validada con un lote de ese tamaño |

Documentos densos, letra difícil, respuestas largas o repetitivas, preparación de PDF, disco lento y uso simultáneo del portátil pueden superar esas ventanas. No se ha establecido una cota de tiempo por página ni un rendimiento garantizado.

### La espera en cola se suma

El tiempo hasta recibir un documento es aproximadamente:

```text
subida + trabajo que queda por delante + preparación y carga + inferencia de sus páginas + descarga
```

Sólo hay un trabajador GPU. Si delante hay tres documentos que aún necesitan aproximadamente cinco minutos cada uno, este documento puede esperar unos quince minutos **antes** de empezar. Es un ejemplo, no una estimación que proporcione la API.

`queued` no significa que se haya bloqueado: significa que el servidor registró el documento y espera turno. Un estado `queued` prolongado puede ser normal cuando hay documentos largos delante. La API no expone posición, páginas ya completadas, tiempo restante ni actividad fina de la GPU; por eso el cliente no puede confirmar desde ese estado cuánto falta.

En batch hay dos esperas distintas:

- `pending` en el manifiesto local: el cliente todavía no lo ha subido, normalmente porque ya hay suficientes trabajos activos o la cola está llena. Dejar el cliente abierto para que lo envíe.
- `queued` en la API: el servidor ya lo tiene. Puede seguir esperando/procesando aunque cierres el cliente, mientras el servidor permanezca activo.

### Cómo evitar impaciencia y envíos duplicados

1. Tras recibir un identificador, **no volver a subir el archivo sólo porque tarde**. Guardar el identificador y consultar el estado cada cinco segundos aproximadamente.
2. Para una primera página corta, reservar alrededor de un minuto. Si tarda varios minutos, consultar el estado; si sigue `queued`, puede estar esperando otros documentos.
3. Si una página corta permanece en `processing` más de 5–10 minutos, avisar al propietario con su identificador para que revise los logs. Es un umbral práctico de consulta, no una prueba de bloqueo ni una orden para reenviar.
4. En PDF largos o lotes, reservar varios minutos o decenas de minutos. Las ventanas de la tabla no incluyen documentos ajenos que estén delante.
5. Si hay un error de conexión, retomar usando el mismo manifiesto. Un timeout del cliente no demuestra que el servidor haya detenido la inferencia.
6. Si el POST perdió la respuesta y no hay identificador confirmado, respetar `submission_uncertain`: pedir revisión al propietario antes de repetirlo.
7. `complete` o `partial`: descargar y revisar. `failed`: leer el error y coordinar un nuevo envío si procede; seguir esperando no cambia ese fallo a éxito.

El cliente de referencia tiene timeout de 120 s **por petición HTTP**, no por la duración total del documento o del lote. Los POST sólo suben y registran el archivo; la inferencia ocurre aparte. No mantener una petición de subida abierta esperando la transcripción. No fijar un timeout global del lote de uno o dos minutos.

El servidor tiene un corte de seguridad de aproximadamente **55 minutos para el motor por documento**, además de preparación, y un timeout externo de una hora para el ejecutor. No es el plazo normal de entrega ni una garantía de que cualquier documento terminará antes. Un lote de muchos documentos puede durar más de una hora porque ese límite se aplica a cada documento. Tampoco limita la espera previa en cola.

### Mensajes recomendados para el cliente que construya el asistente

- Al aceptar: «Documento recibido. Guarda este identificador; no hace falta volver a subirlo».
- En cola: «Esperando turno. Hay una sola GPU y se atienden los documentos secuencialmente».
- En ejecución: «Procesando. Los ejemplos tardaron unos segundos por página; el documento completo puede necesitar varios minutos».
- En lote: mostrar conteos propios de pendientes locales, enviados, descargados, parciales y fallidos, junto con tiempo transcurrido. No mostrar porcentajes ni ETA del servidor como si fueran datos reales.
- Ante demora: «Puedes retomar con el mismo directorio de resultados. Conserva batch_manifest.json».

Estos tiempos provienen de los metadatos originales de 9B para `typed`, `handwritten` y `pdf_page_01`–`pdf_page_08`, y del trabajo de prueba de API `43199fd649e3465c9fd6c226e60efd51`. No se ejecutaron nuevos lotes para producir esta tabla.

## 10. Problemas frecuentes

| Síntoma | Qué comprobar |
|---|---|
| No conecta / tiempo agotado | Portátil encendido y despierto, Wi-Fi correcto, IP actual, API activa y firewall. |
| `TcpTestSucceeded: False` | Revisar el puerto 8090. Una red de invitados o aislamiento Wi-Fi puede impedir comunicación aunque ambos tengan Internet. |
| Ping falla | No prueba por sí solo que la API esté caída; probar el puerto TCP. |
| HTTP `403` | La IP de origen queda fuera del rango permitido; confirmar la red con el propietario. |
| HTTP `404` | Ruta o identificador incorrectos. Usar exactamente los endpoints documentados. |
| HTTP `409` al descargar | El archivo de resultado todavía no está disponible; consultar el estado. |
| HTTP `413` | Archivo demasiado grande o petición sin longitud válida. Usar el cliente o los comandos proporcionados. |
| HTTP `429` | Cola llena; esperar antes de enviar otro trabajo. |
| Estado `failed` | Leer `error`; el propietario debe consultar el log. Puede haber falta de memoria libre, GPU ocupada, PDF inválido/protegido o timeout. |
| Cliente pierde conexión | Guardar el identificador y consultar antes de reenviar para evitar duplicados. |
| Resultado `partial` | Revisar JSON por página; no tratar todo el documento como completo. |
| Servicio reiniciado durante trabajo | El trabajo que estaba procesando se marca `failed`; los que seguían en cola continúan. No hay reanudación por página. |

No ejecutes una segunda instancia del servidor para intentar acelerar: comparte GPU y base de datos con la primera y se bloquea deliberadamente.

## 11. Apéndice para el propietario del portátil

### Activar la API en la intranet

Después de comprobar que no hay otro servidor propio escuchando y cerrar ordenadamente la instancia anterior:

```bash
cd /home/ewok/Documents/ChatGPT/MAP-H-NOV14-CADDOCS
python3 inference_service/server.py --host 192.168.1.14 --port 8090 --allow-network 192.168.1.0/24
```

La dirección predeterminada del programa es `127.0.0.1`: si lo ejecutas sin `--host`, tu hermano no podrá conectarse. Escuchar en la IP Wi-Fi concreta evita enlazar indiscriminadamente a todas las interfaces. No cambiar a una IP pública ni abrir puertos del router.

Comprobar IP y escucha:

```bash
ip -br -4 addr
ss -ltnp 'sport = :8090'
```

Si hay firewall activo, permitir TCP 8090 sólo desde la IP de tu hermano o desde la subred de confianza necesaria. La guía no modifica el firewall ni asume que esté abierto. El acceso efectivo desde el otro equipo debe verificarse allí.

No se utiliza archivo de clave ni variable `OCR_API_TOKEN`. `--allow-network 192.168.1.0/24` permite toda la intranet indicada, por autorización del propietario. Para limitarlo después a un único equipo, reiniciar con `--allow-network IP_DEL_HERMANO/32` sustituyendo el marcador por su IP real. Localhost sigue permitido. Sin `--allow-network`, la aplicación sólo permite clientes de loopback, incluso si escucha en la IP LAN. Este filtro está en la aplicación; no modifica el firewall del sistema.

Los trabajos y resultados están en `inference_service/data/`. Los logs y respuestas detalladas del motor también se guardan en `benchmark/experiments/prompt_pilot_v1/api-IDENTIFICADOR/`. No editar la base de datos ni borrar archivos de trabajos activos.

El servidor no tiene arranque automático configurado. Mantener el portátil despierto y la sesión del servidor activa. No apagarlo ni detener el proceso mientras haya inferencia sin coordinarlo; la cancelación y el apagado ordenado de trabajos aún no están implementados.

### Comprobación conjunta inicial

1. Confirmar IP del servidor: `192.168.1.14` o actualizarla si cambió.
2. Confirmar que escucha en esa IP, puerto 8090.
3. Compartir esta guía, `client.py` y `batch_client.py`.
4. Desde el equipo del hermano: comprobar el puerto y `/health` sin clave.
5. Enviar una imagen pequeña, guardar el identificador y esperar el estado final.
6. Descargar JSON y Markdown y revisar el texto contra la imagen.

La prueba de la API desde el propio servidor usando `http://192.168.1.14:8090/health` fue satisfactoria en la configuración anterior. Tras retirar la autenticación se verificó HTTP 200 sin cabecera Authorization usando la IP de intranet desde el servidor. El servicio acepta el rango 192.168.1.0/24. Las pruebas del cliente por lotes verificaron dos archivos y reanudación sin duplicar solicitudes usando respuestas simuladas; no constituyen una prueba de lote real desde el equipo remoto. **La conexión desde el equipo del hermano debe verificarse siguiendo estos pasos; no se ha comprobado desde ese equipo.**
