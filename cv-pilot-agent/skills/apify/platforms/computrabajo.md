---
name: Platform Computrabajo
description: Configuración específica del scraper de Computrabajo.
scope: SOURCING_PHASE
platform: computrabajo
---

# Platform: Computrabajo Scraper

## Actor
- Nombre: `shahidirfan/computrabajo-jobs-scraper`
- ID: `270QqNecZlrnDMveb`
- Costo de referencia: $0.00199/resultado + $0.0005 arranque. Verificar con `apify actors info shahidirfan/computrabajo-jobs-scraper --json` antes de cotizar.
- ⚠️ Requiere proxies residenciales (configurados en el actor por defecto con `useApifyProxy: true`).

## Input JSON

El actor usa una URL de búsqueda de Computrabajo:

```json
{
  "searchUrl": "[URL_CONSTRUIDA]",
  "maxJobs": [NÚMERO_SOLICITADO],
  "includeFullDescription": true
}
```

### Construcción de URL de búsqueda

Computrabajo usa subdominios por país y rutas con formato específico:

| País | Subdominio |
|------|-----------|
| Colombia | `co.computrabajo.com` |
| Argentina | `ar.computrabajo.com` |
| México | `mx.computrabajo.com` |
| Perú | `pe.computrabajo.com` |
| Chile | `cl.computrabajo.com` |

Formato de URL de búsqueda:
```
https://[SUBDOMINIO]/trabajo-de-[KEYWORD]-en-[LOCATION]
```

**Ejemplos:**
```
https://co.computrabajo.com/trabajo-de-desarrollador-en-medellin
https://co.computrabajo.com/trabajo-de-react-developer-en-bogota
https://ar.computrabajo.com/trabajo-de-backend-en-buenos-aires
```

### Reglas de construcción

- Inferir subdominio del `country`: "CO" → `co.computrabajo.com`, "AR" → `ar.computrabajo.com`, etc.
- Reemplazar espacios con guiones en keyword y location.
- Convertir a minúsculas.
- Si `location` es "Remote", omitir `-en-[location]` de la URL.

## Campo de salida → DB alias

| Campo actor | Alias DB |
|------------|----------|
| title / jobTitle | position |
| company / companyName | company |
| location | location |
| salary | salary |
| url / link | url |
| id | external_id |
| postedAt / date | public_date |
| description | description |

> Los nombres exactos de los campos de salida deben verificarse ejecutando una prueba con 1 job. Los alias listados son los más probables según la documentación del actor.

## Notas específicas

- El actor extrae datos de Computrabajo para múltiples países LATAM (CO, AR, MX, PE, CL, etc.).
- Incluye descripciones completas cuando están disponibles (`includeFullDescription: true`).
- Recomienda proxies residenciales para evitar bloqueos. El actor los configura automáticamente.
- El costo de arranque ($0.0005) se cobra una vez por ejecución, independientemente del número de resultados.
- `maxJobs` puede ser 0 para extraer todos los disponibles (hasta límite de la plataforma).
