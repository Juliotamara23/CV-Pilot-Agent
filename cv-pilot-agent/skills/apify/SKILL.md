---
name: Skill Apify Scraper
description: Interfaz para ejecutar scrapers de Apify y recuperar resultados.
scope: SOURCING_PHASE
---

# Skill: Apify Scraper

## Protocolo de Ejecución (3 pasos)

### 1. Validación de Entorno
Antes de cualquier operación, el agente debe verificar la disponibilidad del CLI:
- Comando: `apify --version`
- Si no está instalado o no responde, informar al usuario: "El CLI de Apify no está instalado en tu entorno. Puedes instalarlo siguiendo la documentación oficial de Apify o continuar pegando tus ofertas manualmente."

### 2. Lanzamiento (Sourcing)
- Comando: `apify call <actor_id> -i <json_input>`
- Validación: Confirmar recepción de `runId`.

### 3. Recuperación (Data Ingestion)
- Comando: `apify dataset get <dataset_id> --format json`
- Normalización: Convertir JSON a "Texto de oferta" estándar antes de pasarlo al Paso 1 (Análisis Técnico).

## Instrucciones para el Agente
- **Estado de Espera:** Durante la ejecución, informar: "Proceso iniciado. Mantendré la sesión en espera hasta que los datos estén listos."
- **Prohibición:** NUNCA ejecutar este paso sin permiso explícito del usuario. Siempre ofrecer la alternativa de entrada manual.

