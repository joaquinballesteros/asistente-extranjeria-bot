# CLAUDE.md — Asistente de Extranjería para Captación (bot de Telegram)

Este archivo es la guía maestra para cualquier agente (Claude Code u otro)
que trabaje en este repositorio. Léelo antes de escribir código. Actualízalo
cuando se tome una decisión de arquitectura nueva o se cierre una fase del
roadmap.

## 0. Estado actual del repositorio

A día de hoy este repositorio **no contiene código todavía**, solo este
documento de planificación y la carpeta `BASE DE DATOS/` con la normativa en
PDF (fuente de datos real, ya presente). Nada de la estructura descrita en
la sección 3 existe aún (`domain/`, `rag/`, `telegram_bot/`, `scripts/`,
`pyproject.toml`, `tests/`), tampoco hay repositorio git inicializado. No
asumas que hay comandos de build/lint/test o código previo que leer: el
primer trabajo real es ejecutar la Fase 0 del roadmap (sección 7).

## 1. Qué estamos construyendo

Bot de Telegram para una gestoría de extranjería, cuyo objetivo de negocio
es **captar clientes**, no solo responder dudas. Orienta a personas
extranjeras sobre trámites (residencia, trabajo, arraigo, reagrupación,
nacionalidad, asilo, menores), usando la normativa real como gancho de
confianza, y deriva a cita con un gestor humano cuando el caso lo requiere
o cuando conviene comercialmente hacerlo.

La normativa fuente vive en `BASE DE DATOS/`, con 8 subcarpetas:

```
BASE DE DATOS/
  01_Legislación_Básica/
  02_Procedimiento Administrativo/
  03_Normativa Comunitarios/
  04_Nacionalidad/
  05_Asilo y Protección Internacional/     ← sensible, forzar Escalar siempre
  06_Menores extranjeros/                   ← sensible, forzar Escalar siempre
  07_Hojas Informativas Oficiales/          ← buena fuente para Autónomo
  08_Modelos Extranjeria y Tasas/           ← formularios/tasas, no RAG conversacional
```

## 2. Stack tecnológico

| Capa | Tecnología | Motivo |
|---|---|---|
| Lenguaje | Python 3.11+ | Buen soporte de librerías de PDF, embeddings y Telegram |
| Bot | `python-telegram-bot`, en modo **long polling** | Solo requiere salida a internet — funciona detrás de NAT, sin IP pública ni puertos abiertos. Evitar modo webhook, que sí necesita un endpoint público |
| Datos estructurados | SQLite (fichero local, `data/app.sqlite3`) | Leads, consentimientos, citas y sesiones de chat sin necesidad de servidor de BD ni coste de hosting adicional |
| Vectores de normativa | Chroma en modo persistente local (`knowledge/data/chroma/`) | Guarda el índice como ficheros locales, pensado para RAG, sin servidor externo |
| Embeddings | Voyage AI (`voyage-law-2`) u OpenAI `text-embedding-3-large` como alternativa | Se llama a la API solo para generar el vector; el almacenamiento sigue siendo 100% local |
| Generación de respuestas | Claude API (Anthropic), vía factoría multi-proveedor (Anthropic/OpenAI/Gemini/DeepSeek) | Ver `rag/llm_client_factory.py`; permite cambiar de proveedor sin tocar código |
| Extracción de PDF | `pypdf` + fallback OCR con `pytesseract` si hace falta | La normativa suele ser texto nativo, pero hay que prever escaneados en `08_Modelos` |
| Excel de reglas | `openpyxl` / `pandas` | Lectura de `LISTADO DE SITUACIONES Y NIVELES DE CONFIANZA.xlsx` |
| Hosting | Máquina local (sin IP pública, con salida a internet) **o** VPS con volumen persistente — ambas opciones válidas gracias al long polling | En local: usar systemd (Linux) o Tarea Programada (Windows) para que el proceso se reinicie solo ante fallos, y evitar que el equipo entre en suspensión — al ser un bot de captación, el tiempo caído es lead perdido |

> Si más adelante el tráfico crece mucho o hace falta más de un proceso del
> bot escribiendo a la vez, se puede migrar a Postgres + pgvector sin tocar
> `domain/` — solo cambia la implementación de `knowledge_base.py` y del
> repositorio de datos. No es necesario anticiparlo ahora. Del mismo modo,
> pasar de máquina local a un VPS es solo mover los ficheros de `data/` y
> `knowledge/data/` — la arquitectura no depende de dónde corra.

## 3. Estructura de carpetas

```
extranjeria_bot/
  domain/                # Lógica pura, sin dependencias de Telegram ni de red
    models.py             # Situacion, Categoria, ConfidenceLevel, UserProfile, NormativaChunk, Lead
    consent.py            # Aviso de protección de datos + registro de consentimiento
    intake.py             # Preguntas dinámicas por situación
    lead_scoring.py       # Señales de conversión: cuándo ofrecer la cita
    knowledge_base.py     # Búsqueda sobre normativa indexada y sobre reglas curadas
    escalation.py         # Modelo de caso derivado + formato para el gestor
    answer_engine.py      # Orquesta todo; ningún import de Telegram
  knowledge/data/         # Índice de Chroma (persistente local) + reglas importadas. No editar a mano.
  rag/                    # Chunking de PDFs, embeddings, retriever, clientes LLM
  telegram_bot/           # Adaptador: teclados, handlers, sesión
  data/
    app.sqlite3            # Leads, consentimientos, citas, sesiones (generado, no versionar en git)
  config.py               # Variables de entorno
  main.py                 # Punto de entrada: arranca el bot con run_polling() (long polling)
scripts/
  ingest_normativa.py      # BASE DE DATOS/*.pdf -> índice Chroma
  import_rules.py          # Excel de situaciones/reglas -> JSON
  backup_data.py            # Copia data/ y knowledge/data/ a almacenamiento externo (cron)
tests/
Normativa y Reglas/
  LISTADO DE SITUACIONES Y NIVELES DE CONFIANZA.xlsx   # fuente de verdad de intake + confianza
BASE DE DATOS/             # PDFs de normativa (ya existe)
README.md                  # Documentación de referencia del proyecto (mantener actualizada)
```

## 4. Modelo de confianza (gobierna todo el comportamiento)

- `Autónomo` → el bot responde directo, citando documento y página.
- `Revisar antes de enviar` → responde igual, pero el caso queda marcado
  para auditoría posterior del gestor.
- `Escalar siempre` → el bot no concluye; recopila datos mínimos y ofrece
  cita. **Por defecto obligatorio** para toda situación de las categorías
  `05_Asilo` y `06_Menores`, sin excepción, aunque la pregunta parezca
  sencilla.

Este modelo vive en el Excel `Normativa y Reglas/LISTADO DE SITUACIONES Y
NIVELES DE CONFIANZA.xlsx`, mantenido por el gestor responsable, no por el
equipo técnico. Cada fila: situación, categoría asociada, preguntas de
intake necesarias, nivel de confianza.

## 5. Flujo de conversación

0. **Aviso de protección de datos + consentimiento explícito**, antes de
   cualquier pregunta de intake. Debe indicar: responsable del tratamiento
   (la gestoría, nombre legal), finalidad (orientar y, si procede, poner en
   contacto con un gestor), derechos ARCO y cómo ejercerlos, enlace a
   política de privacidad completa. Se registra con fecha/hora en
   `domain/consent.py` antes de guardar cualquier dato. Sin esto, no se
   avanza al paso 1.
1. Intake dinámico según la situación (tipo de trámite, nacionalidad,
   tiempo en el país, estado actual).
2. Búsqueda RAG sobre la normativa indexada.
3. Respuesta según nivel de confianza (sección 4).
4. `lead_scoring.py` decide, en paralelo, si mostrar el CTA de cita en ese
   punto — no depende solo de `Escalar siempre` (ver señales en README).
5. Si el usuario acepta cita: pedir teléfono o email de contacto y
   notificar al gestor con el resumen del caso (`escalation.py`). El bot
   no gestiona huecos ni reservas — es el gestor quien da la cita de
   verdad, contactando directamente al cliente.

## 6. Variables de entorno

```
TELEGRAM_BOT_TOKEN=
GESTORES_CHAT_IDS=

LLM_PROVIDER=anthropic        # o: openai | gemini | deepseek | none
LLM_API_KEY=
LLM_MODEL=

DATABASE_URL=sqlite:///data/app.sqlite3
CHROMA_PERSIST_DIR=knowledge/data/chroma
VOYAGE_API_KEY=                # o OPENAI_API_KEY si se usa ese proveedor para embeddings

PRIVACY_POLICY_URL=
DATA_CONTROLLER_NAME=          # nombre legal de la gestoría, para el aviso de consentimiento
```

## 7. Roadmap de tareas

### Fase 0 — Cimientos y compliance (antes de tocar datos reales)
- [ ] Definir estructura del repo según la sección 3 y levantar el
      proyecto Python (`pyproject.toml`, entorno virtual, dependencias base).
- [ ] Configurar almacenamiento local: SQLite (`data/app.sqlite3`, activar
      modo WAL) para datos estructurados y Chroma en modo persistente
      (`knowledge/data/chroma/`) para vectores. Añadir `data/` y
      `knowledge/data/` a `.gitignore` — son datos generados/sensibles, no
      código.
- [ ] Confirmar que el hosting elegido tiene **disco persistente** y
      escribir `scripts/backup_data.py` (copia programada de `data/` y
      `knowledge/data/` a almacenamiento externo).
- [ ] Redactar (con revisión legal externa) el texto exacto del aviso de
      protección de datos y la política de privacidad. **No avanzar a
      producción sin esto**, aunque el desarrollo técnico sí puede seguir
      con un texto provisional.
- [ ] Implementar `domain/consent.py`: modelo de consentimiento, registro
      con timestamp, función que bloquea el avance del flujo si no hay
      consentimiento válido.
- [ ] Crear la plantilla inicial de `Normativa y Reglas/LISTADO DE
      SITUACIONES Y NIVELES DE CONFIANZA.xlsx` con las columnas acordadas
      (situación, categoría, preguntas de intake, nivel de confianza),
      poblada al menos con las situaciones más obvias de `05_Asilo` y
      `06_Menores` marcadas como `Escalar siempre`.

### Fase 1 — Pipeline de normativa (RAG)
- [ ] Implementar extracción de texto por página para los PDFs de
      `BASE DE DATOS/` (prever fallback OCR).
- [ ] Implementar chunking respetando límites de artículo cuando sea
      posible.
- [ ] Implementar `rag/llm_client_factory.py` con al menos el proveedor
      Anthropic funcional (los demás pueden quedar como stubs).
- [ ] Implementar `scripts/ingest_normativa.py`, idempotente (hash de
      archivo para no reprocesar), que escribe al índice de Chroma;
      probado primero con 2-3 PDFs de una sola subcarpeta antes de
      correrlo sobre todo `BASE DE DATOS/`.
- [ ] Implementar `scripts/import_rules.py` para cargar el Excel de
      reglas a `knowledge/data/`.
- [ ] Implementar `domain/knowledge_base.py`: búsqueda combinada
      (situación + retrieval vectorial).

### Fase 2 — Conversación e intake
- [ ] Implementar `domain/models.py` completo (Situacion, Categoria,
      ConfidenceLevel, UserProfile, NormativaChunk, Lead).
- [ ] Implementar `domain/intake.py`: preguntas dinámicas por situación,
      leídas desde las reglas curadas.
- [ ] Implementar `domain/answer_engine.py`: orquesta consentimiento →
      intake → retrieval → nivel de confianza → respuesta.
- [ ] Cobertura de tests con `pytest` sobre todo `domain/`, sin red ni
      Telegram (igual que en el proyecto RIMPE de referencia).

### Fase 3 — Captación y citas
- [ ] Implementar `domain/lead_scoring.py` con las señales iniciales
      (intake completo, preguntas de precio/plazo, número de turnos sin
      CTA mostrado).
- [ ] Implementar `domain/escalation.py`: formato del resumen que recibe
      el gestor (intake + normativa consultada + datos de contacto).
      **Decisión**: no hay reserva de huecos de autoservicio — el bot le
      pide al cliente su teléfono o email al aceptar el CTA, y es el
      gestor quien da la cita de verdad al contactarlo directamente.
- [ ] Implementar `telegram_bot/`: adaptador completo en modo **long
      polling** (`Application.run_polling()` de `python-telegram-bot`, no
      webhook), con teclados para consentimiento e intake con botones
      donde aplique.
- [ ] Notificación a `GESTORES_CHAT_IDS` al agendarse una cita o al
      escalar un caso.

### Fase 4 — Producción y medición
- [ ] Panel o integración con CRM para ver el embudo (usuarios → intake
      completo → CTA mostrado → cita agendada).
- [ ] Métricas básicas de conversión por situación/categoría.
- [ ] Revisión legal final del aviso de protección de datos con datos
      reales del flujo implementado.
- [ ] Evaluar necesidad de soporte multi-idioma según el perfil real de
      usuarios.

## 8. Primer paso para el agente

Al empezar desde cero: ejecutar la Fase 0 completa antes de escribir
ninguna lógica de intake o de RAG. En concreto, no implementar nada que
guarde datos de un usuario real hasta que `domain/consent.py` exista y
esté integrado en el punto de entrada de la conversación — es una
dependencia dura, no una mejora posterior.