# Instrucciones para crear un cliente de la API de transcripción

Este archivo es autosuficiente: entrégalo al asistente de código del equipo cliente. Contiene la configuración real del servidor, el contrato HTTP, requisitos de batch, guía de uso y código de referencia para crear los archivos necesarios. No hace falta recibir un ZIP ni copiar archivos del servidor.

## Encargo para el asistente de código

Implementa en este equipo un cliente para enviar documentos a la API que ya existe en el portátil del hermano. Crea `batch_client.py` a partir del código incluido al final, un README local y las pruebas incluidas. Usa Python 3 y biblioteca estándar; no instales modelos ni un servidor de inferencia en este equipo. Puedes mejorar la interfaz del cliente, pero conserva el contrato descrito y los identificadores de trabajos.

Primero verifica la conectividad y después solicita al usuario una imagen de prueba de su equipo. No envíes carpetas enteras sin que el usuario haya elegido esos archivos. Realiza una prueba pequeña antes de iniciar el lote real. No cambies la configuración del servidor ni abras puertos del router.

### Entregables en el equipo cliente

1. Un comando para enviar un archivo o una carpeta de PDF/PNG/JPEG.
2. Un manifiesto persistente que asocie archivo, SHA-256, identificador y estado.
3. Consulta de progreso y descarga automática de JSON y Markdown por documento.
4. Reanudación de la consulta y las descargas sin volver a enviar trabajos confirmados.
5. Manejo de cola llena, interrupciones de red, documentos fallidos y resultados parciales.
6. Instrucciones para Windows PowerShell y Linux/macOS.
7. Pruebas con respuestas simuladas y un informe de qué se verificó realmente contra el servidor.

## Contrato HTTP real que debe respetar el cliente

### Configuración

- Base URL: **`http://192.168.1.14:8090`**.
- Configurar mediante `OCR_API_URL`, sin barra final.
- Sin clave, sin token y sin cabecera Authorization.
- Acceso permitido temporalmente a `192.168.1.0/24`, además de loopback. Otras redes reciben HTTP 403.
- La dirección del servidor es DHCP: si cambia, el propietario debe comunicar la nueva. No cambiar silenciosamente el servidor asociado a un manifiesto existente.
- No hay HTTPS ni interfaz web de carga. Es un servicio de la intranet de confianza.

### 1. Comprobar servicio

`GET /health` → HTTP 200, JSON:

```json
{"status":"ok","gpu_concurrency":1}
```

Esto sólo comprueba el proceso HTTP. No indica que haya memoria suficiente, que la GPU esté libre ni que un documento vaya a transcribirse correctamente.

### 2. Crear trabajo

`POST /v1/jobs`

- Cuerpo: bytes completos de **un único archivo**.
- Cabeceras: `Content-Type: application/octet-stream` y `Content-Length` correcto.
- No usar multipart, `curl -F`, cuerpo JSON ni una ruta local como sustituto del archivo.
- No usar transferencia chunked: el servidor necesita longitud conocida.
- Éxito: HTTP **202 Accepted** y JSON:

```json
{"job_id":"IDENTIFICADOR_OPACO","status":"queued"}
```

El cliente debe guardar inmediatamente `job_id`. El servidor genera identificadores UUID hexadecimales; tratarlos como cadenas opacas.

La aceptación no garantiza que el archivo sea válido: la preparación y transcripción son posteriores. No se puede elegir modelo, prompt, resolución o prioridad mediante esta ruta. Cada envío aceptado crea un trabajo nuevo: **no hay idempotencia ni deduplicación del servidor**, aunque se envíe dos veces el mismo archivo.

### 3. Consultar estado

`GET /v1/jobs/{job_id}` → HTTP 200, JSON con esta forma ilustrativa:

```json
{
  "id":"IDENTIFICADOR_OPACO",
  "status":"processing",
  "error":null,
  "created":1790000000.0
}
```

Atención: la creación devuelve `job_id`, pero la consulta de estado devuelve **`id`**. `created` es un timestamp Unix en segundos. `error` es nulo o una cadena; puede ser un mensaje técnico resumido y no un diagnóstico completo.

Estados del servidor: `queued`, `processing`, `complete`, `partial`, `failed`. Los tres últimos son terminales para el cliente. Consultar cada cinco segundos aproximadamente; no hacer polling intensivo.

No hay porcentajes, posición de cola, tiempos estimados, webhook ni notificaciones push.

### 4. Descargar JSON

`GET /v1/jobs/{job_id}/result` → HTTP 200, `application/json`:

```json
{
  "job_id":"IDENTIFICADOR_OPACO",
  "model":"qwen3.5-9b",
  "pages":[
    {
      "page":"page_001",
      "text":"Texto transcrito...",
      "status":"complete",
      "finish_reason":"stop",
      "review_status":"unreviewed"
    }
  ]
}
```

Conservar todas las páginas y campos. Las páginas también pueden estar `incomplete` o `failed`; `finish_reason` puede ser `length` o nulo. No reemplazar un resultado parcial por un éxito sin advertencia. Si la ejecución global falla, puede no existir un resultado descargable: no asumir que las páginas procesadas antes del fallo estén disponibles por API.

### 5. Descargar Markdown

`GET /v1/jobs/{job_id}/markdown` → HTTP 200, `text/markdown; charset=utf-8`. Devuelve texto con encabezados por página. Para validar si una página quedó incompleta, consultar el JSON; Markdown no contiene todos sus metadatos.

### Errores HTTP

| Código | Tratamiento del cliente |
|---|---|
| 400 | Solicitud o subida inválida. Corregir antes de repetir. |
| 403 | Origen fuera de la red permitida. Consultar al propietario. |
| 404 | Ruta o trabajo desconocido. No crear otro trabajo automáticamente. |
| 409 | Resultado aún no disponible. Consultar el estado; si el trabajo falló, mostrar el error. |
| 413 | Longitud ausente/inválida, archivo vacío o superior a 30 MiB. |
| 429 | Cola llena. Esperar con pausa; volver a intentar este envío rechazado. |
| Otros / respuesta no JSON | Mostrar código y diagnóstico; no asumir aceptación ni volver a subir automáticamente. |

No se implementa `Retry-After`; el cliente define una pausa razonable. GET puede reintentarse con límite y espera. **Un timeout o una conexión cortada durante POST es ambiguo:** el servidor pudo aceptar el trabajo. Marcarlo `submission_uncertain`, conservar evidencia y pedir revisión al propietario; no reenviar automáticamente. No existe endpoint para listar trabajos ni buscar un envío ambiguo. La revisión de esos casos necesita acceso del propietario a su base de datos/logs.

### Alcance de la cola

La cola del servidor es SQLite persistente. Una sola instancia toma documentos en orden de creación y procesa las páginas de cada documento de forma secuencial. No se ejecutan varios modelos a la vez.

El máximo configurado es 20 trabajos queued/processing. El cliente puede manejar una carpeta mayor: mantiene los pendientes localmente y los envía cuando hay espacio. Tratar 429 como la autoridad sobre la capacidad; no asumir que toda la cola pertenece a este cliente. No abrir múltiples conexiones de subida para intentar acelerar la GPU.

### Reanudación y archivos de salida

- Guardar el manifiesto con escritura temporal y reemplazo; no incluir secretos.
- Mantener al menos: URL, ruta de entrada, SHA-256, estado local, job_id, error y estado final del servidor.
- Guardar un registro de intento antes del POST. Confirmar el identificador después de recibir HTTP 202 válido.
- Evitar volver a enviar pares ruta/huella ya registrados. Un archivo modificado debe tratarse como otra versión.
- No confundir deduplicación local con garantía de idempotencia del servidor.
- Usar nombres de resultados con job_id para evitar colisiones.
- Descargar JSON y MD antes de marcar un trabajo como downloaded; conservar si el estado del servidor era partial.
- No permitir dos procesos cliente escribiendo el mismo manifiesto. El código de referencia requiere respetarlo operacionalmente.
- Si se cambia la URL por una nueva IP del mismo servidor, pedir confirmación y verificar continuidad de identificadores antes de migrar el manifiesto; no reenviar automáticamente.

### Funciones que NO existen en esta API

No hay endpoint de listado, cancelación, borrado, pausa, prioridades, reintento de página, búsqueda, OpenAPI, `/docs`, `/v1/chat/completions` público ni opciones para seleccionar modelos. No inventarlos en el cliente. Un lote de archivos se construye enviando un POST por archivo, no un array ni un ZIP.

## Criterios de aceptación del cliente construido

- Una petición a `/health` funciona sin clave desde el equipo cliente.
- Una imagen pequeña elegida por el usuario produce un job_id, se puede consultar y permite descargar JSON/MD.
- Dos documentos elegidos por el usuario se registran como trabajos distintos y sus resultados se guardan sin sobrescribirse.
- Reiniciar el cliente con el mismo manifiesto no repite esos POST.
- Una respuesta 429 conserva el archivo pendiente; un POST ambiguo no se reenvía automáticamente.
- Un estado partial se muestra y conserva como parcial; failed se muestra con su error.
- Se respetan tamaño, formatos y límites; no se mandan lotes completos para probar conectividad.
- Diferenciar en el informe las pruebas simuladas de las reales; no atribuir al servicio verificación desde este equipo si no se hizo.

## Guía operativa para el usuario y el propietario

La siguiente guía forma parte de este mismo archivo. En ella, las referencias a scripts significan los archivos que el asistente debe crear usando el código incluido al final.

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
2. Los archivos `client.py` y `batch_client.py`, situados en la carpeta `inference_service` del proyecto del servidor. El asistente puede crearlos con el código de referencia incluido al final de este documento.

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


## Código autosuficiente de referencia: cliente por lotes

Guardar este bloque como `batch_client.py` en el equipo cliente. Requiere Python 3 y sólo biblioteca estándar. Es una base funcional con manifiesto, sin interfaz gráfica. Ante errores de red se puede salir y retomar con el mismo directorio; no hay bucle de reconexión infinito. Los códigos HTTP no esperados interrumpen la ejecución para inspección.

```python
"""Submit multiple documents and download results; persistent client manifest."""
import argparse,hashlib,json,os,time,urllib.error,urllib.request
from pathlib import Path
MAX_BYTES=30*1024*1024

def save(path,state):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def request(base,path,data=None):
 headers={'Content-Type':'application/octet-stream'}
 with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=120) as response:return response.read()

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('files',nargs='*',type=Path)
 ap.add_argument('--folder',type=Path,help='PDF/PNG/JPEG files directly inside this folder')
 ap.add_argument('--output-dir',type=Path,default=Path('ocr-results'))
 ap.add_argument('--interval',type=float,default=5)
 args=ap.parse_args()
 base=os.environ['OCR_API_URL'].rstrip('/')
 out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True);manifest=out/'batch_manifest.json'
 state=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'server':base,'files':[]}
 if state['server']!=base:raise SystemExit('Manifest belongs to another server. Use another output directory.')
 files=list(args.files)
 if args.folder:files+=sorted(p for p in args.folder.iterdir() if p.is_file() and p.suffix.lower() in ('.pdf','.png','.jpg','.jpeg'))
 known={(r['path'],r['sha256']) for r in state['files']}
 for path in files:
  path=path.resolve()
  if not path.is_file() or not 0<path.stat().st_size<=MAX_BYTES:raise SystemExit(f'Invalid file or size >30 MiB: {path}')
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  if (str(path),digest) not in known:
   state['files'].append(dict(path=str(path),sha256=digest,status='pending',job_id=None));known.add((str(path),digest))
 if not state['files']:raise SystemExit('Specify files or --folder, or resume an existing output directory.')
 save(manifest,state)
 while True:
  active=sum(r['status'] in ('queued','processing') for r in state['files'])
  for row in state['files']:
   if row['status']=='pending' and active<20:
    path=Path(row['path']);body=path.read_bytes()
    if hashlib.sha256(body).hexdigest()!=row['sha256']:raise SystemExit(f'File changed: {path}')
    # Mark BEFORE POST: a lost response must never trigger a duplicate automatically.
    row['status']='submission_uncertain';save(manifest,state)
    try:job=json.loads(request(base,'/v1/jobs',body))
    except urllib.error.HTTPError as e:
     if e.code==429:
      row['status']='pending';save(manifest,state);break
     row['error']=f'HTTP {e.code}';save(manifest,state);raise
    row.update(job_id=job['job_id'],status='queued');active+=1;save(manifest,state)
    print(f"Submitted {path.name}: {row['job_id']}",flush=True)
   if row['job_id'] and row['status'] in ('queued','processing','complete','partial'):
    job=json.loads(request(base,'/v1/jobs/'+row['job_id']))
    row['status']=job['status'];row['error']=job.get('error');save(manifest,state)
    print(f"{Path(row['path']).name}: {row['status']}",flush=True)
    if row['status'] in ('complete','partial'):
     prefix=out/(Path(row['path']).stem+'-'+row['job_id'])
     for endpoint,suffix in [('result','.json'),('markdown','.md')]:
      body=request(base,f"/v1/jobs/{row['job_id']}/{endpoint}")
      path=prefix.with_name(prefix.name+suffix);path.write_bytes(body)
     row['server_status']=row['status'];row['status']='downloaded';save(manifest,state)
  if not any(r['status'] in ('pending','queued','processing','complete','partial') for r in state['files']):break
  time.sleep(max(1,args.interval))
 summary={s:sum(r['status']==s for r in state['files']) for s in ['downloaded','failed','submission_uncertain']}
 print(json.dumps(summary),flush=True)
 if summary['submission_uncertain']:print('A submission has no confirmed ID. Ask the owner to inspect the queue before resubmitting.',flush=True)
 return 1 if summary['failed'] or summary['submission_uncertain'] else 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except (OSError,urllib.error.URLError) as e:raise SystemExit(f'{e}\nResume with the same --output-dir. Do not delete batch_manifest.json.')
```

## Código opcional: cliente de un documento

Guardar como `client.py`. Es un ejemplo mínimo: crea un trabajo cada vez que se ejecuta. Para reanudación y batch usar el cliente anterior.

```python
"""Usage: OCR_API_URL=http://private-address:8090 python3 client.py file.pdf"""
import argparse,json,os,time,urllib.request
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('file',type=Path);ap.add_argument('--output',type=Path,default=Path('ocr-result.json'));args=ap.parse_args()
base=os.environ['OCR_API_URL'].rstrip('/');headers={}
def call(path,data=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=120))
job=call('/v1/jobs',args.file.read_bytes())['job_id'];print('Job:',job,flush=True)
while True:
 state=call('/v1/jobs/'+job);print(state['status'],flush=True)
 if state['status'] in ('complete','partial'):break
 if state['status']=='failed':raise SystemExit(state.get('error','Failed'))
 time.sleep(5)
args.output.write_text(json.dumps(call('/v1/jobs/'+job+'/result'),ensure_ascii=False,indent=2),encoding='utf-8');print(args.output)
```

## Pruebas del cliente por lotes

Guardar como `test_batch_client.py` junto a `batch_client.py`. Estas pruebas simulan HTTP y no envían documentos al servidor ni consumen GPU.

```python
import contextlib,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import batch_client as client

class BatchTests(unittest.TestCase):
 def test_multiple_files_and_resume_without_duplicate_submission(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);files=[root/'one.png',root/'two.png']
   for file in files:file.write_bytes(b'test image bytes')
   jobs=[]
   def fake(base,path,data=None):
    if data is not None:
     jid=str(len(jobs)+1);jobs.append(jid);return json.dumps({'job_id':jid}).encode()
    if path.endswith('/result'):return b'{"pages": []}'
    if path.endswith('/markdown'):return b'# Page\nText'
    return b'{"status":"complete"}'
   argv=['batch_client.py',*[str(p) for p in files],'--output-dir',str(root/'out')]
   with patch.dict(os.environ,{'OCR_API_URL':'http://test'},clear=True),patch.object(client,'request',side_effect=fake),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(client.main(),0);self.assertEqual(client.main(),0)
   self.assertEqual(len(jobs),2)
   self.assertEqual(len(list((root/'out').glob('*.md'))),2)
   self.assertEqual(len(list((root/'out').glob('*-[12].json'))),2)
 def test_lost_upload_response_is_not_resubmitted(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);file=root/'one.png';file.write_bytes(b'test')
   argv=['batch_client.py',str(file),'--output-dir',str(root/'out')]
   with patch.dict(os.environ,{'OCR_API_URL':'http://test'},clear=True),patch.object(sys,'argv',argv),patch.object(client,'request',side_effect=OSError('lost response')) as req,contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaises(OSError):client.main()
    self.assertEqual(client.main(),1);self.assertEqual(req.call_count,1)

if __name__=='__main__':unittest.main()
```

Ejecutar en esa carpeta:

```powershell
py -3 -m unittest test_batch_client -v
```

En Linux/macOS:

```bash
python3 -m unittest test_batch_client -v
```

## Mejoras opcionales del cliente, sin cambiar el servidor

Tras lograr el flujo básico se puede añadir selección gráfica de carpeta, bloqueo de manifiesto, filtros recursivos explícitos, descargas atómicas y reintentos acotados de GET. Mantener sin reintento automático los POST ambiguos. No afirmar procesamiento exactamente una vez: la API todavía no proporciona idempotencia.
