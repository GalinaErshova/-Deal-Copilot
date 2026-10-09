# Deal Copilot

AI-assisted presale and tender decision system.

**Core principle:** AI reads and structures documents; deterministic code calculates labor, cost, margin and BID/NO BID.

## MVP scope implemented in `feat/mvp-0-3`

### MVP-0 — documents
- FastAPI + SQLite + SQLAlchemy.
- Upload PDF/DOCX/XLSX.
- Parsing layer adapted from the proven Ask-Learn mechanics.
- Original vs parsed document review UI.
- Model Gateway with MiMo provider and mock fallback.
- Structured extraction + human confirmation.
- Full pipeline log with inputs/outputs/warnings.

### MVP-1 — labor
- Demo productivity reference.
- Labor-hours, FTE and physical staff calculation.

### MVP-2 — economics
- Revenue, direct/full cost, profit and margin.
- Break-even and target-price calculation.
- Price sensitivity scenarios.

### MVP-3 — decision
- Deterministic BID / BID WITH CONDITIONS / NO BID.
- Conditions are returned separately from the decision.

## Stack

- Frontend: Next.js + React + TypeScript
- Backend: FastAPI + Python
- Database: SQLite + SQLAlchemy
- LLM gateway: provider abstraction; first provider is Xiaomi MiMo
- Default model: `mimo-v2.6-flash`
- MiMo OpenAI-compatible base URL: `https://api.xiaomimimo.com/v1`

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
pip install -e .[dev]
copy .env.example .env
# Set MIMO_API_KEY and DEMO_MODE=false for real MiMo calls.
uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm ci
copy .env.example .env.local
npm run dev
```

Open http://localhost:3000

Set the API URL in `frontend/.env.local` with `NEXT_PUBLIC_API_URL`.

Calculation defaults, labor assumptions, demo reference values, upload limits,
accepted formats, prompt version, locale and currency are read from backend
settings. `backend/.env.example` lists their environment variable names and
demo defaults. In demo mode, extraction returns no invented fields; enter and
confirm the area manually before running a calculation. Uploaded files are
limited by the configured per-file, total-size and file-count settings.

## Calculation and proposal consistency

Each saved calculation records its assumptions, service rows, formulas and a fingerprint of
the persisted deal inputs. The calculation history remains available after documents,
confirmed fields, service lines or catalog data change, but an outdated calculation cannot
be exported as a current proposal. Recalculate and confirm the deal first. The proposal
uses the contract term and line prices saved with that calculation.

Document extraction stops with an explicit error when the configured text limit is exceeded;
the pipeline records the omitted character count. Increase the limit or reduce the input
set before retrying. Backend tests cover these behaviors; the frontend build checks types
and compilation. Browser acceptance requires a running local app.

PDF text inside an empty geometric table frame is kept as a paragraph, so a false table
detection cannot silently remove that text from extraction.

## Secret handling

Never commit API keys. `.env` is ignored. Only placeholders belong in `.env.example`.

## Architecture boundary

The Model Gateway isolates business code from a specific LLM provider. MiMo is the first provider, not a hard dependency of extraction/business logic.

The document review approach is intentionally based on the Ask-Learn UX: source document on the left, parsed/structured representation on the right, with traceability at every later step.

# Локальная MiMo для теста

Для локальной проверки можно использовать community-конверсию Xiaomi MiMo-7B-RL
в GGUF Q4_K_M. Оригинальный API-ключ MiMo в `backend/.env` менять не нужно:
локальный режим обращается к `127.0.0.1` и использует отдельный локальный
провайдер.

1. Скачайте CPU-сборку `llama.cpp` из [официальных релизов](https://github.com/ggml-org/llama.cpp/releases)
   и поместите `llama-server.exe` и DLL в `./.local-model/runtime/`.
2. Скачайте [MiMo-7B-RL-Q4_K_M.gguf](https://huggingface.co/jedisct1/MiMo-7B-RL-GGUF)
   в `./.local-model/` (файл около 4,68 ГБ).
3. Запустите сервер: `./scripts/start-local-mimo.ps1`.
4. В отдельном окне PowerShell задайте параметры только для текущего процесса и
   запустите backend:

   ```powershell
   $env:LLM_PROVIDER = "local"
   $env:DEMO_MODE = "false"
   $env:MIMO_BASE_URL = "http://127.0.0.1:8080/v1"
   $env:LLM_DEFAULT_MODEL = "mimo-7b-rl-q4_k_m"
   $env:LLM_COMPLEX_MODEL = "mimo-7b-rl-q4_k_m"
   cd backend
   uvicorn app.main:app --reload
   ```

Файлы модели и рантайма хранятся в `.local-model/`, исключённой из Git.
Q4 — экспериментальная 4-битная конверсия; перед использованием извлечённые
значения и цитаты необходимо сверять с исходными документами.

В локальном режиме длинный запрос автоматически делится на части размером
`LLM_INPUT_CHUNK_CHARS` (по умолчанию 12 000 символов), чтобы не превышать окно
контекста модели. Результаты объединяются, а разные значения одного поля
помечаются как противоречие. Для ошибки модели интерфейс показывает текст
причины, а не сырой JSON ответа API.

Облачная модель может вернуть оценку уверенности словами вместо числа или
пустую строку вместо списка противоречий или null вместо статуса поля. Известные
уровни уверенности нормализуются по `EXTRACTION_CONFIDENCE_LABEL_MAP`; неизвестный
уровень сохраняется как отсутствие оценки. Пустой статус становится `extracted`,
а текст противоречия сохраняется как описание. Эти необязательные неточности
формата не прерывают разбор всего набора документов.

## Разбор и сверка документов

По умолчанию загрузка принимает PDF, DOCX, PPTX, XLSX, RTF, MHT/MHTML, HTML,
Markdown и TXT. Список задаётся через `ACCEPTED_UPLOAD_EXTENSIONS` и используется
как серверным API, так и формой загрузки.

Файлы сохраняются до обработки и остаются доступны при ошибке разбора или модели.
Результат содержит упорядоченные абзацы, страницы, слайды и таблицы с путями к
исходным блокам. Таблицы хранят строки и ячейки отдельно; текст для извлечения
связывает значения с заголовками столбцов. Если явная шапка таблицы не задана,
первая строка используется как заголовок и добавляется предупреждение для сверки.

В окне сверки PDF показывается встроенно, а офисные и текстовые форматы — как
структурированный предпросмотр; исходный файл всегда можно скачать. Требования с
проверенной цитатой и путём подсвечиваются в распознанном тексте. В карточке требования
источник показывается по имени исходного файла и человекочитаемому месту (страница,
абзац, таблица или слайд); цитата раскрывается до полного предложения из распознанного
блока, а исходный подтверждённый фрагмент остаётся подсвеченным. Полоса хода
показывает число разобранных файлов и переход к извлечению моделью; внутренний
ход генерации моделью не транслируется, поэтому на этом этапе процент остаётся
оценочным.

Площади из таблиц с адресами и заголовком площади раскладываются на отдельные строки
по объекту и виду работ; итоговые строки вроде «Итого» не суммируются повторно.
Режимы «ежедневно», «еженедельно» и «ежемесячно» переводятся в число смен из настроек;
для работ по заявкам и нераспознанных графиков пользователь задаёт плановое количество.
График и цитата из источника видны при вводе и в результате. Трудоёмкость считается
детерминированно по каждой строке; экономика — по общей площади сделки и общим ставкам.
Ставка 800 м²/смену подставляется только для регулярной уборки помещений из справочника
выработки. Сейчас это демонстрационный MVP-норматив, не утверждённая корпоративная норма.
Для уборки снега автоматической ставки нет: её нужно задать отдельно.

## Навигация, трудоёмкость и КП

Основная цепочка работы содержит этапы «Новая сделка», «Документы», «Требования»,
«Трудоёмкость», «Экономика» и «Коммерческое предложение». Кнопки «Назад» и
«Далее» находятся под рабочим блоком. Служебный журнал запуска вынесен в нижнюю
часть боковой панели; панель можно скрыть, чтобы развернуть рабочую область.

В «Трудоёмкости» адрес, вид работ, площадь, ставка выработки, режим и число
смен показаны вместе. После расчёта там же появляется таблица по строкам;
«Экономика» показывает общие показатели сделки. Источники площади, режима и
вида работ открываются стрелкой рядом с соответствующим полем. Пояснение
выработки и чувствительности к цене доступно через значок `i`.

На этапе «Коммерческое предложение» можно скачать редактируемый `.docx` с
подтверждёнными условиями и результатом последнего расчёта. Реквизиты заказчика
(название, адрес, ИНН/КПП, ОГРН, представитель, телефон и почта) автоматически
ищутся в уже разобранных документах сделки; стрелка у найденного поля открывает
исходный фрагмент, значения можно исправить вручную. Данные исполнителя и срок
действия заполняются отдельно. Не найденные реквизиты остаются пустыми, без
догадок. Банковские реквизиты заказчика в КП не переносятся. Себестоимость,
прибыль и маржа в файл не включаются; перед отправкой проверьте реквизиты,
налоговый режим и договорные условия.

Сканированные страницы PDF без текстового слоя отмечаются предупреждением.
Локальный OCR-движок в текущем окружении не установлен; изображения внутри MHT
также пока не распознаются.

Извлечение строк и их проверка разделены на локальные модули: `backend/app/scope_extractor.py`
находит адрес, вид площади, площадь и подтверждающий фрагмент; `backend/app/scope_curator.py`
проверяет наличие строки в источнике и конфликтующие площади. Куратор не исправляет данные
автоматически и не вызывает облачную модель. Вид уборки и режим привязываются только при наличии
подтверждающего текста. Единое подтверждение расчёта сбрасывается после изменения любого
исходного значения или допущения.
# Ручные услуги и настройка формул

На вкладке «Требования» можно добавить услугу, которой нет в извлечённых документах:
указать адрес, вид площади, вид работ и площадь. Ручные строки сохраняются отдельно
от цитат из документов и включаются в общий расчёт вместе с документными строками.
Для каждой строки на вкладке «Трудоёмкость» задаются выработка и режим уборки;
изменения ручных строк сохраняются автоматически.

Общий прайс-лист компании редактируется в разделе «Настройки компании» →
«Прайс-лист услуг». Позиция хранит название, вид площади, описание работ, тариф
за м² в месяц, необязательную выработку и примечание. При добавлении ручной услуги
выбор позиции подставляет её параметры; адрес и площадь задаются для текущей сделки.
Тариф каждой строки входит в расчёт отдельно, а общий тариф и маржа считаются по
сумме стоимости строк. Позиции прайса можно убрать из выбора или вернуть; уже
сохранённые строки сделок сохраняют цену, с которой были созданы.

В разделе «Настройки компании» → «Формулы расчёта» можно менять формулы трудозатрат,
себестоимости, тарифов КП и маржинальности. Настройки хранятся в локальной базе
приложения и применяются при следующем расчёте. Для маржинальности результат задаётся
долей (например, `0.2` означает `20%`). Редактор принимает только числа, разрешённые
переменные и арифметические операции `+`, `-`, `*`, `/` со скобками; выполнение
произвольного кода недоступно. Названия допустимых переменных показаны под каждой
формулой.
