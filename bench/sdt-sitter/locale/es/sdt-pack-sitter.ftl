# Español. La referencia es locale/en/sdt-pack-sitter.ftl: cualquier
# identificador que falte aquí recurre al inglés sin lanzar excepción
# (ticket 0692).
#
# La unidad de trabajo es UN ARCHIVO ADJUNTO, nunca la referencia que lo
# contiene. La interfaz de Zotero traduce *item* de un modo que se lee como la
# referencia, así que ningún texto de aquí lo emplea: se dice archivo. «Pack» es
# el nombre interno del artefacto y no aparece en ninguna pantalla.

## El botón de la barra de herramientas, y la información que muestra al pasar

index = Índice
index-coverage = Índice { $percent } %
scope-one = Biblioteca: { $names }
scope-few = Bibliotecas: { $names }
scope-many = Todas las bibliotecas ({ $count })

files-indexed = { $count ->
        [one] { $count } archivo indexado
       *[other] { $count } archivos indexados
    }

## Cada fase que un lector puede encontrar, en sus propias palabras

phase-census = Recuento
phase-extracting = Indexación en curso
phase-error = Error
phase-disabled = Desactivado
phase-native-worker-busy = En espera: indexación nativa en curso
phase-cpu-busy = En pausa: procesador ocupado
phase-low-memory = En pausa: memoria insuficiente
phase-low-disk = En pausa: espacio en disco insuficiente
phase-storage-unavailable = En pausa: almacenamiento no disponible
phase-resources-unavailable = En pausa: recursos del sistema ilegibles
phase-launch-declined = Sin iniciar: desactive y vuelva a activar la extensión

## El marco de la ventana de estado

dialog-title = Asistente de indexación
section-global = Progreso global — biblioteca
section-active = Indexación en curso
details-title = Detalles
fulltext-title = Índice de búsqueda de texto completo
fulltext-body = Índice de búsqueda de texto completo de Zotero (distinto del índice que prepara el asistente):
fulltext-unavailable = Estadísticas no disponibles: { $error }
tech-title = Diagnóstico técnico

## Capa 1: el progreso, lo que se está procesando y cuándo debería terminar

files-indexed-of = Archivos indexados: { $current } / { $total }
files-indexed-count = Archivos indexados: { $current }
global-estimate = Fin estimado hacia { $median } (entre { $low } y { $high })
active-none = Ninguna indexación en curso
active-file = Indexando: { $file } — { $progress } % — { $elapsed } transcurridos
active-finalising = Finalizando…
active-references = Analizando las referencias…
active-estimate = Duración estimada: { $median } (entre { $low } y { $high })

files-failed = { $count ->
        [one] { $count } archivo no se pudo indexar
       *[other] { $count } archivos no se pudieron indexar
    }

## Capa 2: los recuentos y el ajuste en que se apoyan las estimaciones

observations-waiting = Duraciones observadas: { $count } (hacen falta 3 antes de estimar)
observations = Duraciones observadas: { $count }
observations-basis = Duraciones observadas: { $count } — base de cálculo: { $basis }
basis-pages = por página
basis-bytes = por octeto
diagnostics-phase = Estado: { $phase }
diagnostics-census = Recuento: { $scanned } / { $total }
diagnostics-count = { $status }: { $count }
diagnostics-completed = Creados en esta sesión: { $count }
diagnostics-failed = No se pudieron indexar (último recuento): { $count }
diagnostics-error = Error: { $error }
cache-not-saved = Caché no guardada: { $error }

## Capa 3: lo que pide un informe de fallo y un lector nunca lee

debug-label = Registrar cada paso en la salida de depuración de Zotero
journal-copy = Copiar el registro
journal-copied = Registro copiado al portapapeles.
journal-copy-failed = No se pudo copiar: portapapeles no disponible.
journal-unreadable = Registro ilegible: { $error }
environment-version = Versión de la extensión: { $version }
environment-zotero = Zotero: { $version } (compatibilidad declarada { $min } – { $max })
environment-native = Formato nativo: versión { $format }, esquema { $schema }
environment-extractors = Extractores nativos: { $extractors }
environment-root = Instalada en: { $root }
admission-none = Ninguna medición de recursos desde el arranque.
admission-age = Última medición hace { $age } — una lectura por admisión, ninguna mientras la biblioteca esté al día
admission-memory = Memoria disponible: { $available } (umbral { $threshold })
admission-load = Carga del procesador: { $load } sobre { $cpus } núcleos
admission-disk = Espacio en disco: { $available } (umbral { $threshold })

## Las cantidades, y cómo se nombra un archivo

gibibytes = { $value } GiB
unknown-value = ?
unit-seconds = { $count } s
unit-minutes = { $count } min
unit-hours-minutes = { $hours } h { $minutes } min
unit-minutes-seconds = { $minutes } min { $seconds } s
file-unknown = archivo desconocido
file-number = archivo n.º { $id }
settle-failed = Error en «{ $file }»: { $error }
resources-read = Lectura de recursos: { $error }

## El aviso de arranque, cuyo cuerpo son estos cuatro mensajes, en orden

launch-title = Asistente de indexación — experimental
launch-question = ¿Indexar toda la biblioteca esta noche?
launch-conditions = Un archivo cada vez, con al menos 4 GiB de memoria disponible y 8 GiB de disco libre. Los PDF y los ajustes del índice de búsqueda de texto completo quedan intactos.
launch-worker = El proceso compartido no se puede interrumpir ni recibir una prioridad de sistema propia. Un archivo grande puede retrasar un trabajo nativo llegado después. Los umbrales no limitan su consumo.
launch-disable = Desactivar la extensión detiene las admisiones; el archivo en curso termina. Los errores quedan confinados a la sesión. Una caché local desechable conserva las comprobaciones y las duraciones; no contiene ni texto ni tarea activa.
