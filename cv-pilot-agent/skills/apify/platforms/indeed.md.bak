---
name: Platform Indeed
description: Configuración específica del scraper de Indeed.
scope: SOURCING_PHASE
platform: indeed
---

# Platform: Indeed Scraper

## Actor
- Nombre: `misceres/indeed-scraper`
- Costo de referencia: $0.003/resultado (verificar siempre vía `apify actors info misceres/indeed-scraper --json` antes de cotizar al usuario)

## Input JSON
```json
{
  "position": "[EXTRACTED_POSITION]",
  "country": "[EXTRACTED_COUNTRY]",
  "location": "[EXTRACTED_LOCATION]",
  "maxItemsPerSearch": [INT_NUMBER],
  "parseCompanyDetails": true,
  "saveOnlyUniqueItems": true,
  "followApplyRedirects": false
}
```

> Opcional: `startUrls` permite scrapear URLs directas de Indeed. No usar cuando se busca por keywords.

## Campo de salida → DB alias
| Campo actor | Alias DB |
|------------|----------|
| positionName | position |
| company | company |
| location | location |
| salary | salary |
| url | url |
| id | external_id |
| postedAt | public_date |
| description | description |
| postedAt (fecha real) | postingDateParsed → public_date |
