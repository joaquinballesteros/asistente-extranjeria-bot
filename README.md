# Asistente de Extranjería para Captación (bot de Telegram)

Bot de Telegram para una gestoría de extranjería. Orienta a personas
extranjeras sobre trámites (arraigo, renovaciones, tarjeta de familiar de
la UE, estudios, reagrupación familiar, asilo, nacionalidad) usando
normativa real como gancho de confianza, y deriva a cita con un gestor
humano cuando el caso lo requiere o conviene comercialmente.

Ver [CLAUDE.md](CLAUDE.md) para la guía completa de arquitectura, modelo
de confianza, flujo de conversación y roadmap de desarrollo.

Esta guía está pensada para poder seguirse **sin experiencia previa en
programación**. Vas a usar la "terminal" (una ventana donde se escriben
comandos en vez de hacer clic) — cada paso te dice exactamente qué
escribir.

## 1. Descargar lo necesario

Antes de tocar el proyecto, instala esto en tu ordenador (una sola vez):

| Programa | Para qué | Enlace de descarga |
|---|---|---|
| Python 3.11 o superior | Ejecutar el bot | [python.org/downloads](https://www.python.org/downloads/) |
| Git | Descargar el código del repositorio | [git-scm.com/downloads](https://git-scm.com/downloads) |
| Tesseract OCR | Leer PDFs escaneados | Windows: [instalador UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) · macOS: se instala con Homebrew (paso siguiente) · Linux: `apt` (paso siguiente) |
| Poppler | Convertir páginas de PDF a imagen para el OCR | Windows: [poppler-windows (release más reciente)](https://github.com/oschwartz10612/poppler-windows/releases) · macOS/Linux: paso siguiente |
| Homebrew (solo macOS) | Instalar Tesseract y Poppler | [brew.sh](https://brew.sh) |

Además necesitas:
- Un bot de Telegram: habla con [@BotFather](https://t.me/BotFather) en
  Telegram, escribe `/newbot`, sigue sus instrucciones y guarda el
  **token** que te da (una cadena larga tipo `123456:ABC-...`).
- Una API key de **al menos un** proveedor de LLM para generar las
  respuestas: [Anthropic](https://console.anthropic.com),
  [Google AI Studio](https://aistudio.google.com) (Gemini) u
  [OpenAI](https://platform.openai.com).
- Una API key de **al menos un** proveedor de embeddings para indexar la
  normativa: [Voyage AI](https://www.voyageai.com) u OpenAI (la misma de
  arriba sirve).

### Windows: pasos importantes durante la instalación

- **Python**: en el instalador, marca la casilla **"Add python.exe to
  PATH"** antes de darle a Install. Si no la marcas, los comandos de más
  abajo no funcionarán.
- **Tesseract**: durante la instalación, en la pantalla de selección de
  componentes, marca también el paquete de idioma **Spanish**.
- **Poppler**: no tiene instalador, es una carpeta de programas ya
  compilados. Descarga el `.zip` de la release, descomprímelo en un sitio
  fijo (por ejemplo `C:\poppler`), y añade su subcarpeta `Library\bin` al
  PATH del sistema:
  1. Busca en el menú de inicio "Editar las variables de entorno del sistema" (o "Edit the system environment variables").
  2. Botón "Variables de entorno...".
  3. En "Variables de usuario", selecciona `Path` → "Editar" → "Nuevo".
  4. Pega la ruta completa a la carpeta `Library\bin` dentro de donde descomprimiste Poppler (por ejemplo `C:\poppler\Library\bin`).
  5. Acepta todo y **cierra y vuelve a abrir** la terminal para que el cambio surta efecto.

## 2. Descargar el proyecto

Abre una terminal:
- **Windows**: busca "Símbolo del sistema" (o "cmd") en el menú de inicio.
- **macOS**: busca "Terminal" en Spotlight (⌘+Espacio).
- **Linux**: tu terminal habitual.

Y ejecuta:

```bash
git clone <url-del-repositorio>
cd asistente-extranjeria-bot
```

(Alternativa sin Git: en la página del repositorio en GitHub, botón verde
"Code" → "Download ZIP", y descomprímelo.)

## 3. Instalar el proyecto

**macOS**, para instalar Poppler y Tesseract con Homebrew (si aún no
tienes Homebrew, instálalo primero desde [brew.sh](https://brew.sh)):

```bash
brew install poppler tesseract tesseract-lang
```

**Linux (Debian/Ubuntu)**:

```bash
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-spa
```

Ahora, en las tres plataformas, crea el entorno virtual de Python e
instala las dependencias del proyecto:

**macOS / Linux**:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Windows** (símbolo del sistema):

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

> Si usas PowerShell en vez de "Símbolo del sistema" y `.venv\Scripts\Activate.ps1`
> da un error de "no se puede cargar porque la ejecución de scripts está
> deshabilitada", ejecuta antes: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

Deberías ver `(.venv)` al principio de la línea de la terminal: significa
que el entorno está activado. **Cada vez que abras una terminal nueva
para trabajar en el proyecto, tienes que volver a activar el entorno**
con el comando `source .venv/bin/activate` (o `.venv\Scripts\activate` en
Windows) antes de ejecutar nada.

## 4. Configurar las claves

Copia la plantilla de configuración:

```bash
cp .env.example .env      # macOS / Linux
copy .env.example .env    # Windows
```

Abre el fichero `.env` con cualquier editor de texto (Bloc de notas
sirve) y rellena los valores (ver sección 6 de `CLAUDE.md` para el
detalle de cada variable):

```
TELEGRAM_BOT_TOKEN=          # el token que te dio @BotFather
GESTORES_CHAT_IDS=           # ids de chat de Telegram de los gestores, separados por comas (puede quedar vacío por ahora)

LLM_PROVIDER=anthropic       # anthropic | gemini | openai | deepseek | none
LLM_API_KEY=                 # tu API key de ese proveedor
LLM_MODEL=                   # el modelo que quieras usar de ese proveedor

VOYAGE_API_KEY=              # o OPENAI_API_KEY, para generar embeddings
```

### Cómo conseguir los `GESTORES_CHAT_IDS`

Cuando un cliente acepta una cita, el bot le envía el resumen del caso (con
su teléfono o email) a cada uno de estos chats de Telegram, para que el
gestor le dé la cita contactándolo directamente. **No es el `@usuario` de
Telegram, es un número** (el "chat ID"). Para conseguirlo:

1. Pide a cada gestor que le escriba `/start` a tu bot (el mismo que
   creaste con @BotFather) desde su cuenta de Telegram.
2. Abre esta URL en el navegador, sustituyendo `<TOKEN>` por el valor de
   `TELEGRAM_BOT_TOKEN` de tu `.env`:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Busca en el resultado un bloque como este y anota el número de `"id"`
   dentro de `"chat"` — ese es el chat ID de esa persona:
   ```json
   "chat": { "id": 123456789, "first_name": "...", "type": "private" }
   ```
4. Repite con cada gestor y pon todos los IDs en `.env`, **separados por
   comas y sin espacios**:
   ```
   GESTORES_CHAT_IDS=123456789,987654321
   ```

(Alternativa más rápida sin usar la URL de arriba: que cada gestor le
escriba a [@userinfobot](https://t.me/userinfobot) en Telegram, que le
devuelve directamente su chat ID.)

Si dejas `GESTORES_CHAT_IDS` vacío, el bot sigue funcionando con
normalidad; simplemente no se notifica a nadie cuando se acepta una cita.
Después de cambiar `.env` tienes que **reiniciar el bot** (parar con
`Ctrl+C` y volver a lanzar `python extranjeria_bot/main.py`) para que
recoja el cambio.

## 5. Añadir la normativa

**El corpus de normativa en PDF no se distribuye por git** (por tamaño y
para no redistribuir documentación oficial sin control de versión).
Tienes que colocar tu propia copia en una carpeta `BASE DE DATOS/` en la
raíz del proyecto, respetando esta estructura de subcarpetas (ver sección
1 de `CLAUDE.md`):

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

Carga el Excel de reglas curadas a formato JSON (ya viene incluido en el
repositorio, en `Normativa y Reglas/`):

```bash
python scripts/import_rules.py
```

Indexa la normativa. Prueba primero con 2-3 PDFs de una sola subcarpeta
antes de indexar todo el corpus (el pipeline es idempotente: si vuelves a
ejecutarlo, solo reprocesa los ficheros que hayan cambiado):

```bash
python scripts/ingest_normativa.py --only "07_Hojas Informativas Oficiales" --limit 3
python scripts/ingest_normativa.py   # todo BASE DE DATOS/, cuando confirmes que va bien
```

## 6. Arrancar el bot

```bash
python extranjeria_bot/main.py
```

Se queda corriendo en la terminal en modo *long polling* (no necesita IP
pública ni configuración de red). Para pararlo, pulsa `Ctrl+C` en esa
misma terminal. Mientras esté corriendo, puedes hablarle a tu bot desde
la app de Telegram.

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
  configurado (`launchd` en macOS, `systemd` en Linux, Tarea Programada en
  Windows) — hay que lanzar el proceso a mano.
- El menú de situaciones no cubre casos de menores extranjeros (decisión
  de producto: este bot está pensado para autoservicio de personas
  adultas).
