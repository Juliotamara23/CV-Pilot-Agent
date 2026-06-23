---
name: Onboarding Conversacional
description: Flujo conversacional para recolectar, extraer, verificar y persistir el perfil del usuario en data/. Reemplaza la subida manual de archivos estáticos.
scope: GLOBAL
---

# Onboarding Conversacional

## 0. Requisitos

- **Entorno virtual de Python** (`.venv/`) en `cv-pilot-agent/` — contiene `pymupdf` y aísla la dependencia del Python del sistema.
- **PyMuPDF** (`fitz`) — necesario para extraer texto y enlaces desde archivos PDF (Camino B). Se instala dentro del venv.
- Compatible con Windows (PowerShell), Linux y macOS.

### Resolucion del interprete (venv-first)

El agente DEBE resolver el interprete de Python segun la siguiente prioridad:

1. Si existe `cv-pilot-agent/.venv/Scripts/python.exe` (Windows) o `cv-pilot-agent/.venv/bin/python` (Unix) → usar el Python del venv.
2. Si no existe el venv → usar `python` (Windows) o `python3` (Unix) del sistema como fallback.

Tabla de referencia Rapida:

| Plataforma | venv existe | Python | pip |
|------------|-------------|--------|-----|
| Windows    | si          | `cv-pilot-agent\.venv\Scripts\python.exe` | `cv-pilot-agent\.venv\Scripts\pip.exe` |
| Windows    | no          | `python` | `pip` |
| Unix       | si          | `cv-pilot-agent/.venv/bin/python` | `cv-pilot-agent/.venv/bin/pip` |
| Unix       | no          | `python3` | `pip3` |

> Nota: las rutas del venv son relativas a `cv-pilot-agent/`. Ajustar el prefijo (`cv-pilot-agent/...` o `.\cv-pilot-agent\...`) segun el directorio de trabajo del agente.

### Protocolo de setup (consentimiento obligatorio, una sola pregunta)

El agente NUNCA crea el venv ni instalaPyMuPDF sin permiso explicito. Seguir este protocolo con una **unica** pregunta:

1. **Detectar si el venv existe:**
   - Windows: `Test-Path -LiteralPath "cv-pilot-agent\.venv\Scripts\python.exe"`
   - Unix: `[[ -x cv-pilot-agent/.venv/bin/python ]]`

2. **Si el venv existe** → verificar PyMuPDF con el Python del venv (ver Deteccion abajo). Si PyMuPDF falla, reinstalar con el pip del venv (ver Instalacion). No preguntar al usuario.

3. **Si el venv NO existe → informar al usuario con una sola pregunta:**
   > "El entorno de PDF no está configurado. Para procesar archivos PDF (Camino B) creo un entorno virtual con PyMuPDF. ¿Desea que lo configure automáticamente? Si prefiere hacerlo manual, ejecute el script de setup. Si no desea soporte PDF, continuaré solo con el Camino A (pegar el texto del CV)."

4. **Segun la respuesta:**
   - **Aceptar setup automatico** → ejecutar el script de la plataforma:
     - Windows: `pwsh -File cv-pilot-agent/scripts/setup.ps1` (o `.\scripts\setup.ps1` desde `cv-pilot-agent/`)
     - Unix: `bash cv-pilot-agent/scripts/setup.sh`
     - Si el setup falla, informar el error y ofrecer el Camino A como fallback. No insistir.
   - **Preferir manual** → mostrar el comando del script correspondiente para que el usuario lo ejecute. Continuar la sesion en Camino A hasta que el venv exista.
   - **No desea soporte PDF** → deshabilitar el Camino B para esta sesión y todas las futuras. Solo ofrecer Camino A (texto). Anotar en `data/preferencias.md`: `pdf_soporte: false`.

### Deteccion de PyMuPDF (usando el interprete resuelto)

```powershell
# Windows, venv existe
cv-pilot-agent\.venv\Scripts\python.exe -c "import fitz; print('OK')" 2>&1
# Windows, sin venv (fallback)
python -c "import fitz; print('OK')" 2>&1
```

```bash
# Unix, venv existe
cv-pilot-agent/.venv/bin/python -c "import fitz; print('OK')" 2>&1
# Unix, sin venv (fallback)
python3 -c "import fitz; print('OK')" 2>&1
```

Si el comando imprime `OK`, PyMuPDF está listo. Si muestra `ModuleNotFoundError`, no está instalado.

### Instalacion de PyMuPDF (usando el pip del venv)

Si el venv existe pero PyMuPDF no está instalado, reinstalar con el pip del venv (nunca con el pip del sistema):

```powershell
# Windows, venv existe
cv-pilot-agent\.venv\Scripts\pip.exe install pymupdf
```

```bash
# Unix, venv existe
cv-pilot-agent/.venv/bin/pip install pymupdf
```

Si el venv no existe (fallback), usar el pip del sistema como antes:

```powershell
# Windows, sin venv
pip install pymupdf
```

```bash
# Unix, sin venv
pip3 install pymupdf
```

### Nota sobre permisos
En el modo fallback (sin venv) algunos sistemas Linux/macOS pueden requerir `pip install --user pymupdf` o `pip3 install pymupdf`. En Windows con PowerShell, `pip install pymupdf` funciona sin modificaciones adicionales. Cuando el venv existe, el pip del venv no requiere `--user` ni permisos extra.

## Objetivo
Guiar al usuario, mediante una conversación, para recolectar su CV, datos de contacto, ejemplos de correos y preferencias. El agente extrae la información, la verifica con el usuario y la persiste en archivos Markdown dentro de `data/`.

## Archivos de Salida
- `data/perfil.md` — CV unificado y datos de contacto (fuente única de verdad, sin duplicación).
- `data/correos.md` — ejemplos de correos para mimetismo de estilo.
- `data/preferencias.md` — preferencias del usuario (mimetismo, sector, tono, idioma).

Los templates de referencia están en `skills/onboarding/templates/`.

## Preparación del Directorio
`data/` es creado por el agente bajo demanda. No existe `.gitkeep` (está excluido de git). Antes de escribir, crear el directorio si no existe.

## Paso 1: Detección de Estado

Al iniciar la sesión, verificar el contenido de `data/`:

1. **Si `data/perfil.md` existe y contiene los campos requeridos** (Identidad, Contacto, Experiencia):
   - Cargar el perfil de forma silenciosa y continuar el flujo normal.
   - No iniciar onboarding.

2. **Si `data/perfil.md` no existe o está incompleto:**
   - Verificar si existe un estado de onboarding parcial en `data/.onboarding-state.md`.
   - Si existe estado parcial, retomar desde el último paso completado (Paso 5).
   - Si no existe estado parcial, iniciar onboarding desde el Paso 2.

3. **Compatibilidad con flujo anterior:**
   - Si `data/` está vacío pero existe `resources/identidad.md`, ofrecer al usuario migrar sus datos al nuevo flujo. No asumir la migración automáticamente.

## Paso 2: Presentación del Flujo

Mensaje al usuario (neutral, sin voseo, sin jerga regional):

> Antes de empezar a buscar vacantes, necesito configurar tu perfil. Voy a pedirte tu CV, tus datos de contacto, algunos ejemplos de correos que hayas escrito y tus preferencias de búsqueda. Puedes pegar el texto directamente o subir un PDF. Empecemos por tu CV.

## Paso 3: Recolección del CV

Antes de ofrecer los caminos, ejecutar la detección de PyMuPDF (ver sección 0. Requisitos).

Ofrecer los caminos disponibles según el resultado:

- **Camino A (texto):** Siempre disponible. El usuario pega el contenido del CV en el chat.
- **Camino B (PDF):** Solo disponible si PyMuPDF está instalado. El usuario sube un archivo PDF. El agente ejecuta `scripts/pdf_parser.py` para extraer texto y enlaces.

Si PyMuPDF no está instalado, ofrecer solo el Camino A y mencionar que el soporte para PDF estará disponible cuando se instale la dependencia.

### Manejo del Camino B
1. Ejecutar usando el interprete resuelto (seccion 0. Requisitos):
   - Windows, venv existe: `cv-pilot-agent\.venv\Scripts\python.exe scripts\pdf_parser.py <ruta_al_pdf>`
   - Windows, sin venv: `python scripts/pdf_parser.py <ruta_al_pdf>`
   - Unix, venv existe: `cv-pilot-agent/.venv/bin/python scripts/pdf_parser.py <ruta_al_pdf>`
   - Unix, sin venv: `python3 scripts/pdf_parser.py <ruta_al_pdf>`
2. Leer la salida JSON:
   - `ok: true` → usar `text` y `links`.
   - `ok: false` → informar al usuario que no se pudo procesar el PDF y ofrecer el Camino A (pegar texto) o pegar enlaces manualmente.
3. Los enlaces extraídos (LinkedIn, GitHub, etc.) se guardan para el Paso 4.

### Validación Semántica (VSI)
Aplicar la validación del CV recibido:
- Detectar secciones clave (Experiencia, Skills, Educación, Contacto).
- Si el documento no tiene estructura de CV profesional, rechazar con firmeza:
  > Este documento no parece un CV profesional válido. Por favor, comparte un CV real.
- Continuar solo con un CV válido.

## Paso 4: Extracción de Campos

A partir del CV (texto o PDF) y de los enlaces extraídos, el agente identifica:

- Nombre completo
- Resumen profesional
- LinkedIn (de los enlaces o del texto)
- GitHub (de los enlaces o del texto)
- WhatsApp / teléfono
- Correo electrónico
- Link al CV (Drive, repositorio, etc.) — opcional
- Experiencia (puestos, empresas, periodos, logros)
- Educación
- Skills técnicos

Si falta un campo esencial (LinkedIn, GitHub, teléfono o correo), pedirlo explícitamente:
> Encontré tu CV, pero me falta tu [campo]. Puedes pegarlo aquí.

## Paso 5: Verificación con el Usuario (Obligatoria)

Antes de escribir cualquier archivo, presentar un resumen de todo lo extraído y pedir confirmación explícita. NUNCA escribir archivos sin confirmación.

> Resumen de tu perfil:
> - Nombre: ...
> - LinkedIn: ...
> - GitHub: ...
> - Teléfono: ...
> - Experiencia: ...
>
> ¿Es correcto? Responde "sí" para confirmar o indica qué hay que corregir.

- Si el usuario confirma → continuar al Paso 6.
- Si el usuario corrige → aplicar correcciones y volver a presentar el resumen.

## Paso 6: Recolección de Correos y Preferencias

Pedir ejemplos de correos y preferencias:

> Para redactar con tu estilo personal, necesito 2 o 3 ejemplos de correos que hayas enviado en postulaciones anteriores. Pégalos aquí. Si no tienes, podemos omitirlo y usaré un tono profesional estándar.

> Por último, tus preferencias:
> - Sector preferido (por ejemplo: Backend, IA, Fullstack)
> - Tono (formal, cercano, técnico)
> - Idioma de postulación (español, inglés)

> ¿Quieres que guarde los correos generados como borradores en Gmail? Así podrás revisarlos antes de enviarlos. (sí/no)

> ¿Quieres que guarde los correos generados como borradores en Outlook? Así podrás revisarlos antes de enviarlos. (sí/no)

Guardar las respuestas en `data/preferencias.md` como `gmail_drafts: sí` o `gmail_drafts: no` y `outlook_drafts: sí` o `outlook_drafts: no`. Si el usuario omite la pregunta de Outlook, registrar `outlook_drafts: no` por defecto.

Si el usuario omite los correos, escribir `data/correos.md` con una nota indicando que no se proporcionaron ejemplos.

## Paso 7: Backup y Escritura

Antes de sobrescribir un archivo existente en `data/`, crear un respaldo:

- Copiar `data/perfil.md` a `data/perfil.md.bak` (si existe).
- Copiar `data/correos.md` a `data/correos.md.bak` (si existe).
- Copiar `data/preferencias.md` a `data/preferencias.md.bak` (si existe).

Luego escribir los tres archivos usando los templates como estructura de referencia.

## Paso 8: Confirmación y Limpieza

- Confirmar al usuario que el perfil está configurado.
- Eliminar `data/.onboarding-state.md` si existe (onboarding completado).
- Continuar con el flujo normal del orquestador.

## Estado de Onboarding Parcial (Reanudación)

Para soportar abandono y reanudación entre sesiones, después de cada paso completado, escribir `data/.onboarding-state.md` con:

```
ultimo_paso_completado: <número de paso>
campos_recolectados: <lista>
```

Al retomar, leer este archivo y continuar desde el paso siguiente al último completado. No volver a pedir datos ya recolectados.

## Reglas de Idioma
Todo texto dirigido al usuario debe estar en español neutral: sin voseo, sin jerga regional. Mantener un tono profesional, cálido y directo.

## Fallback
Si el usuario decide no completar el onboarding en este momento, registrar el estado parcial y continuar con un perfil estándar. El orquestador no debe insistir en la misma sesión.
