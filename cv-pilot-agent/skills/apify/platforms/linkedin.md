---
name: Platform LinkedIn
description: Configuración específica del scraper de LinkedIn.
scope: SOURCING_PHASE
platform: linkedin
---

# Platform: LinkedIn Scraper

## Actor
- Nombre: `curious_coder/linkedin-jobs-scraper`
- ID: `hKByXkMQaC5Qt9UMN`
- Costo de referencia: $0.001/resultado. Verificar con `apify actors info curious_coder/linkedin-jobs-scraper --json` antes de cotizar.

## Input JSON

El actor usa URLs de búsqueda de LinkedIn (no keywords directos). Construir la URL a partir de los parámetros del usuario:

```json
{
  "urls": ["URL_CONSTRUIDA"],
  "scrapeCompany": true,
  "count": [NÚMERO_SOLICITADO],
  "splitByLocation": false
}
```

### Construcción de URL de búsqueda

LinkedIn usa parámetros en la URL para filtrar:

```
https://www.linkedin.com/jobs/search/?keywords=[POSITION]&location=[LOCATION]&f_WT=[WORKPLACE]&f_E=[EXPERIENCE]
```

| Parámetro | Descripción | Valores |
|-----------|-------------|---------|
| `keywords` | Término de búsqueda (position) | URL-encoded |
| `location` | Ciudad o región (location) | URL-encoded |
| `geoId` | ID de ubicación (opcional) | numérico |
| `f_WT` | Workplace type | 1=presencial, 2=remoto, 3=híbrido |
| `f_E` | Experience level | 2=entry, 3=mid, 4=senior |
| `f_TPR` | Time posted | r86400=24h, r604800=semana |
| `sortBy` | Orden | R=más reciente |

**Ejemplo:**
```
https://www.linkedin.com/jobs/search/?keywords=React%20Developer&location=Medell%C3%ADn&f_WT=2&f_E=3
```

### Reglas de construcción

- El agente DEBE construir la URL automáticamente, NUNCA pedir al usuario que la genere.
- Si `country` es "CO" y `location` es una ciudad colombiana, no incluir `location=` como texto plano sino usar el nombre de la ciudad.
- Si el usuario pide "remoto/híbrido", usar `f_WT=2` o `f_WT=3`.
- Mínimo `count`: 10. Si el usuario pide menos, informar que LinkedIn requiere al menos 10 pero solo se analizarán los primeros [N].

## Campo de salida → DB alias

| Campo actor | Alias DB |
|------------|----------|
| title | position |
| companyName | company |
| location | location |
| link | url |
| id | external_id |
| postedAt | public_date |
| description (plain text) | description |
| salary (salaryInsights) | salary |
| applyUrl | — |
| workplaceTypes | — |
| country | — |
