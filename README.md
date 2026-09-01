# Asistente de Extranjería para Captación (bot de Telegram)

Bot de Telegram para una gestoría de extranjería. Orienta a personas
extranjeras sobre trámites (arraigo, renovaciones, tarjeta de familiar de
la UE, estudios, reagrupación familiar, asilo, nacionalidad) usando
normativa real como gancho de confianza, y deriva a cita con un gestor
humano cuando el caso lo requiere o conviene comercialmente.

Ver [CLAUDE.md](CLAUDE.md) para la guía completa de arquitectura, modelo
de confianza, flujo de conversación y roadmap de desarrollo.

## Requisitos previos

- Python 3.11 o superior.
- [Homebrew](https://brew.sh) (macOS) o el gestor de paquetes de tu
  distribución (Linux), para el motor de OCR.
- Una cuenta de bot de Telegram (token de [@BotFather](https://t.me/BotFather)).
- Una API key de al menos un proveedor de LLM (Anthropic, Gemini u OpenAI)
  y de al menos un proveedor de embeddings (Voyage AI u OpenAI).

### OCR (extracción de PDFs escaneados)

El pipeline de ingesta usa OCR como fallback para páginas escaneadas
(`extranjeria_bot/rag/pdf_extraction.py`). Necesita los binarios de
`poppler` y `tesseract` instalados en el sistema (no son paquetes de
Python):

```bash
# macOS
brew install poppler tesseract tesseract-lang

# Debian/Ubuntu
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-spa
```

## Puesta en marcha

```bash
git clone <url-del-repositorio>
cd asistente-extranjeria-bot

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
```

Rellena `.env` con tus valores (ver sección 6 de `CLAUDE.md` para el
detalle de cada variable):

```
TELEGRAM_BOT_TOKEN=          # token de @BotFather
GESTORES_CHAT_IDS=           # ids de chat de Telegram de los gestores, separados por comas

LLM_PROVIDER=anthropic       # anthropic | gemini | openai | deepseek | none
LLM_API_KEY=
LLM_MODEL=

VOYAGE_API_KEY=              # o OPENAI_API_KEY, para generar embeddings
```

### Normativa (BASE DE DATOS/)

**El corpus de normativa en PDF no se distribuye por git** (está en
`.gitignore` por tamaño y por evitar redistribuir documentación oficial
sin control de versión). Tienes que colocar tu propia copia en
`BASE DE DATOS/`, respetando la estructura de subcarpetas que espera el
pipeline de ingesta (ver sección 1 de `CLAUDE.md`):

```
BASE DE DATOS/
  01_Legislación_Básica/
  02_Procedimiento Administrativo/
  03_Normativa Comunitarios/
  04_Nacionalidad/
  05_Asilo y Protección Internacional/
  06_Menores extranjeros/
  07_Hojas Informativas Oficiales/
  08_Modelos Extranjeria y Tasas/       # no se indexa (no es RAG conversacional)
```

### Cargar las reglas curadas

El Excel `Normativa y Reglas/LISTADO DE SITUACIONES Y NIVELES DE
CONFIANZA.xlsx` sí está en el repositorio (es contenido de negocio
curado, no un dato generado). Cárgalo a JSON:

```bash
python scripts/import_rules.py
```

### Indexar la normativa

Prueba primero con 2-3 PDFs de una sola subcarpeta antes de indexar todo
el corpus (el pipeline es idempotente: si vuelves a ejecutarlo, solo
reprocesa los ficheros que hayan cambiado):

```bash
python scripts/ingest_normativa.py --only "07_Hojas Informativas Oficiales" --limit 3
python scripts/ingest_normativa.py   # todo BASE DE DATOS/, cuando confirmes que va bien
```

### Arrancar el bot

```bash
python extranjeria_bot/main.py
```

Se queda corriendo en primer plano en modo *long polling* (no necesita IP
pública ni webhook). Párralo con `Ctrl+C`.

## Tests

```bash
pytest
pytest --cov=extranjeria_bot.domain --cov-report=term-missing   # con cobertura
```

Toda la lógica de negocio (`extranjeria_bot/domain/`) tiene cobertura de
tests sin red ni Telegram: los tests aíslan Chroma y las reglas curadas en
directorios temporales, y usan un cliente de embeddings y de LLM falsos.

## Limitaciones conocidas

- El aviso de protección de datos es un **borrador provisional sin
  revisión legal** (`extranjeria_bot/domain/consent.py`). No usar en
  producción sin que lo revise alguien con criterio legal.
- El estado de una conversación en curso vive en memoria del proceso del
  bot (`extranjeria_bot/telegram_bot/session.py`), no en base de datos: si
  el proceso se reinicia a mitad de una conversación, el usuario retoma
  desde `/start`. Los consentimientos y los leads sí son duraderos
  (SQLite).
- No hay todavía un mecanismo de arranque automático/reinicio ante fallos
  configurado (`launchd` en macOS, `systemd` en Linux) — hay que lanzar el
  proceso a mano.
- El menú de situaciones no cubre casos de menores extranjeros (decisión
  de producto: este bot está pensado para autoservicio de personas
  adultas).
