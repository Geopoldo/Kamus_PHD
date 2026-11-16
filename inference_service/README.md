# API privada de transcripción

Para la intranet actual (`192.168.1.14:8090`), ver [la guía detallada para el cliente](GUIA_HERMANO_INTRANET.md). Incluye envío por lotes con `batch_client.py`, consulta y descarga de resultados. La VPN sólo aplica si se conectan desde redes distintas.

Primera versión para dos equipos. Usa Python 3 y Pillow existentes, SQLite y el motor local 9B. Una sola instancia y un trabajador GPU. No instalar modelos en el cliente.

> Estado: API sin clave habilitada en `192.168.1.14:8090`, con clientes permitidos de `192.168.1.0/24` y loopback.

## Arrancar

Desde la raíz del proyecto:

```bash
python3 inference_service/server.py
```

Por defecto escucha exclusivamente en localhost:8090. Para esta intranet arrancar con `--host 192.168.1.14 --port 8090 --allow-network 192.168.1.0/24`. Por petición del propietario, la API no exige clave: cualquier equipo del rango permitido con acceso a ese puerto puede enviar trabajos y recuperar resultados si conoce su identificador. Mantener el acceso limitado a la intranet de confianza.

## Cliente

Definir BASE como `http://192.168.1.14:8090`. Subir bytes directamente (no multipart):

```bash
curl -H 'Content-Type: application/octet-stream' --data-binary @documento.pdf "$BASE/v1/jobs"
curl "$BASE/v1/jobs/IDENTIFICADOR"
curl "$BASE/v1/jobs/IDENTIFICADOR/result" -o resultado.json
curl "$BASE/v1/jobs/IDENTIFICADOR/markdown" -o resultado.md
```

Estados: queued, processing, complete, partial, failed. Cada página incluye texto y estado de revisión unreviewed. Complete indica ejecución terminada, no verificación de exactitud.

## Límites y operación

30 MiB por archivo, 50 páginas PDF, 25 millones de píxeles por imagen, 20 trabajos pendientes/activos. Una inferencia simultánea; GPU vigilada con reservas del benchmark. El servidor de modelo carga por documento y se descarga al terminar. El portátil debe estar encendido y despierto.

La cola y los resultados persisten. Tras reinicio, trabajos interrumpidos se marcan failed y deben reenviarse; los queued continúan. No hay aún reanudación por página, cancelación, deduplicación, búsqueda, separación entre usuarios ni limpieza automática. No hay autenticación; cualquier equipo que alcance el servicio puede consultar los trabajos conocidos. Usar sólo entre personas de confianza.

No hay progreso fino por página en esta versión. No es aún un servicio público de producción. Los PDFs se renderizan con pdftoppm a un máximo de 2200 píxeles de lado para controlar recursos; validar calidad sobre documentos reales. El máximo de una hora por documento es un corte operacional, no garantía de tiempo.

La referencia Astra no se envía al modelo. Los resultados son literales con el prompt original; nombres y fechas requieren revisión.
