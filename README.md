# AlgoFusion 2 Pipeline

> Актуальный рабочий контур: `Incoming` -> `file-monitor` -> Redis -> `worker-pipeline-v2` -> `shared/files` -> FastAPI `api` -> React UI `ui-web`.
> Новый UI открыт на `http://localhost:8080`. Старый Streamlit UI в `ui/` оставлен только как fallback.

## О проекте

`Algofusion` - это контур автоматической обработки входящих документов. Система принимает PDF и изображения, готовит страницы к OCR, распознает текст, определяет тип документа, собирает структуру, извлекает поля и сохраняет итоговый JSON.

Основная рабочая версия - `pipeline_v2`. Она обрабатывает документ внутри одного worker-контейнера, чтобы не терять контекст между очисткой изображения, OCR, анализом страниц, извлечением полей и финальной нормализацией.

## Что входит в текущий production-контур

- `Incoming` - локальная входящая папка. Если в ней появляется PDF/PNG/JPG/JPEG, документ автоматически попадает в обработку.
- `file-monitor` - контейнер-наблюдатель. Он ждет, пока файл полностью запишется, копирует оригинал в `shared/files/<document>/original/` и создает задачу.
- `redis` - очередь задач, статусы и события.
- `worker-pipeline-v2` - основной OCR/pipeline worker. Он забирает задачу из Redis, запускает `pipeline_v2` и пишет артефакты.
- `api` - FastAPI-слой над артефактами, review-правками и событиями.
- `ui-web` - новый React-интерфейс оператора: документы, поля, артефакты, события, ручные правки, светлая/темная тема.

Минимальный пользовательский сценарий:

1. Положить файл в `Incoming`.
2. Дождаться обработки worker-ом.
3. Открыть `http://localhost:8080`.
4. Проверить итоговый JSON, проблемные поля и артефакты во вкладках UI.

Поддерживаемые типы документов:

- `waybill` - накладная.
- `invoice` - инвойс.
- `payment_order` - платежное поручение.
- `account_prot` - протокол согласования/счет-протокол.

Поддерживаемые входные форматы:

- `pdf`
- `png`
- `jpg`
- `jpeg`

Главный результат обработки:

- `data/final_json/<document>.json`

Промежуточные PNG и JSON сохраняются рядом с документом в рабочей папке. Они нужны для диагностики, ручной проверки качества и повторного запуска без полного OCR, если сырой OCR уже есть.

## Как движется документ

1. Файл появляется во входящей папке `Incoming`.
2. `file-monitor` проверяет, что файл полностью записан, определяет тип файла и создает рабочую папку документа в `shared/files`.
3. Оригинал копируется в `original/`.
4. Для документа формируется Pydantic-контракт `FileJob`.
5. `FileJob` отправляется в Redis-очередь `files:pipeline_v2`.
6. `worker-pipeline-v2` забирает задачу из Redis и запускает `pipeline_v2`.
7. Страницы рендерятся из PDF или берутся из изображения.
8. Для каждой страницы выполняется очистка изображения и подготовка PNG для OCR.
9. OCR формирует сырой JSON с распознанными блоками текста.
10. Page-level логика определяет роль страницы, тип документа, признаки таблиц, шапки, футера и служебных зон.
11. Document-level логика собирает страницы в один документ и формирует предварительный JSON.
12. Нормализация приводит поля к единому виду, восстанавливает безопасно восстанавливаемые значения и помечает сомнительные поля.
13. Финальный JSON сохраняется в `data/final_json`.
14. Статусы и события публикуются в Redis, чтобы UI мог показывать журнал и прогресс.

## Основные директории

`core/`

- Общие сервисы приложения: работа с Redis, регистрация файлов, статусы и события.

`monitor/`

- Контейнер `file-monitor`.
- Следит за входящей папкой, создает задачи и кладет их в Redis.

`api/`

- FastAPI-интерфейс для нового UI.
- Читает документы, поля, артефакты и события из `shared/files`/Redis.
- Сохраняет ручные правки оператора в `data/review_overrides/ui_review.json`, не затирая исходный `final_json`.

`workers/OCR-Sergei/PIPELINE_V2/`

- Основной worker обработки документов.
- Содержит OCR-контур, модульный runtime pipeline и Dockerfile worker-а.

`shared/`

- Общие контракты, настройки, JSON-утилиты, логирование, ресурсы и словари.
- `shared/resources/dictionaries/` и `shared/resources/review/` содержат выносные YAML-ресурсы для словарей, review-правил и текстовых нормализаторов.
- Папка `shared/files` используется как рабочее хранилище артефактов и исключена из git.

`ui/`

- Старый Streamlit-интерфейс мониторинга.
- Оставлен как fallback и для совместимости, но основной рабочий UI теперь находится в `ui-web/`.

`ui-web/`

- Новый React/Vite UI на порту `8080`.
- Показывает обзор набора, документы, проверку полей, артефакты и события.
- Для полей показывает русское смысловое название и технический path.
- Поддерживает светлую/темную тему и подсказки по ключевым действиям.

`scripts/`

- Служебные CLI/smoke-скрипты для локальной проверки без UI.

`tests/`

- Быстрые unit-тесты ключевых runtime-модулей.
- OCR в этих тестах не запускается.

## Основные файлы pipeline v2

`workers/OCR-Sergei/PIPELINE_V2/src/modules/pipeline_v2.py`

- Точка входа worker-а.
- Забирает задачи из очереди и запускает обработку документа.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime.py`

- Координирующий runtime-слой.
- Связывает рендеринг, очистку, OCR, анализ структуры, fallback-логику и финальную сборку.
- Чувствительные доменные блоки постепенно вынесены в отдельные модули, чтобы `runtime.py` оставался точкой orchestration, а не единственным монолитом.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_page_ops.py`

- Операции над страницами: cleaner, stage1-артефакты, запуск OCR по странице.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_render.py`

- Рендеринг PDF/изображений и преобразования между PIL/OpenCV.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_regions.py`

- Общие операции над OCR-строками и ROI-регионами.
- Группирует OCR-блоки по строкам, собирает строку таблицы в pipe-формат и читает сохраненные ROI-регионы для downstream fallback-логики.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_structure.py`

- Построение role-aware структуры документа.
- Используется для понимания, какие страницы относятся к одному документу и какую роль выполняет каждая страница.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_segmentation.py`

- Сегментация страниц и выбор профиля структуры.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_page_signals.py`

- Page-level анализ признаков страницы.
- Определяет сигналы по шапке, таблице, footer-зонам, document hints и role hints до document-level сборки.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_waybill_header.py`

- Логика кропа шапки накладной.
- Отдельно отвечает за извлечение номера накладной из верхней части документа.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_waybill_raw.py`

- Raw fallback для накладных по OCR/ROI-строкам страницы.
- Восстанавливает шапку, стороны документа, основание, итоговые суммы и служебные поля накладной, когда основной структурный JSON неполный или содержит шум.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_invoice_items.py`

- Нормализация invoice-товаров: единицы измерения, артикулы, описание, barcode-зоны и канонизация item-строк.
- Здесь же находится разбор строк товарной таблицы инвойса и проверки `qty/unit/money/vat` для invoice overlay и raw fallback.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_invoice_raw.py`

- Сырой fallback-парсер invoice по OCR-строкам страницы.
- Изолирует извлечение шапки инвойса, сбор item-блоков и fallback-сборку итоговых полей без смешивания с остальным runtime-кодом.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_invoice_postprocess.py`

- Invoice overlay, raw fallback и финальная постобработка invoice-полей.
- Отвечает за восстановление строк по OCR/ROI, определение ставки НДС по странице, очистку примечаний и финальную нормализацию item-строк.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_numeric_reconciliation.py`

- Проверка связанных числовых полей в товарных строках.
- Если числа можно восстановить надежно, поле заполняется.
- Если арифметика не сходится или опор недостаточно, вся связанная числовая группа помечается как `проверить поле`.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_postprocess.py`

- Page-level постобработка результата LLM/ROI перед сборкой документа.
- Применяет fallback-логики по типам документов, дозаполняет безопасные поля, очищает шумные значения и сохраняет `_page_role`/`_page_id` для дальнейшей сборки.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_documents.py`

- Document-level сборка результата после обработки страниц.
- Собирает многостраничный документ, объединяет item-строки, выбирает шапку/хвост документа, запускает финальную нормализацию и сохраняет промежуточные JSON-артефакты.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_account_prot.py`

- Вспомогательная логика для account protocol.
- Содержит распознавание заголовка таблицы и точечный ремонт смещенных числовых колонок в строках этого типа документа.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_text_quality.py`

- Проверка качества текста.
- Сюда вынесены признаки OCR-мусора, смешения латиницы/кириллицы и финальная маркировка сомнительных текстовых полей.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_money_words.py`

- Работа с суммами прописью.
- Используется для восстановления русских денежных строк по числовым итогам, когда это безопасно.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_waybill_text.py`

- Постобработка текстовых полей накладной после извлечения.
- Содержит нормализацию номера документа, approval-полей, денежных строк прописью, единиц измерения и финальную очистку item-строк.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_numbers.py`

- Общие числовые утилиты: мягкий парсинг чисел, сравнение с допуском, поля связанных числовых групп.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_io.py`

- Чтение/запись файлов, создание директорий, сохранение PNG/JSON/TXT. JSON читается и пишется через общий UTF-8 helper с `orjson`-ускорением при наличии библиотеки.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/runtime_common.py`

- Общие helpers для bbox, OCR-текста, ключевых слов и безопасного доступа к зонам.

`workers/OCR-Sergei/PIPELINE_V2/src/modules/`

- Это канонический runtime-слой пайплайна.
- Здесь живут page/document orchestration, fallback-логика по типам документов, финальная нормализация и document-specific модули `runtime_invoice_*`, `runtime_waybill_*`, `runtime_payment_order_*`, `runtime_account_protocol_*`.
- Новые словари и кириллические правила выносятся в `shared/resources`, а не размазываются по runtime-функциям.

## Статусы, null и `проверить поле`

В финальном JSON используются два разных случая:

- `null` означает, что поле действительно пустое или для него нет значения.
- `проверить поле` означает, что OCR или арифметическая проверка показали сомнительный результат и требуется просмотр оператором.

Для товарных таблиц действует консервативное правило: если одно из связанных числовых полей строки нельзя надежно восстановить, то на проверку отправляется вся связанная числовая группа. Это безопаснее, чем частично оставлять числа, которые могут выглядеть правдоподобно, но не сходиться по расчетам.

## Настройки

Основные настройки задаются через переменные окружения и читаются через `pydantic-settings`.

Важные переменные:

- `HOST_INCOMING_PATH` - локальная входящая папка для `file-monitor`.
- `HOST_SHARED_FILES_PATH` - локальная папка для рабочих артефактов.
- `ALGOFUSION_RUN_ROOT` - run-root, который читает новый API/UI. Для live-режима удобно задавать `/shared/files`; для benchmark-прогона можно указать конкретную папку вроде `/shared/files/_no_ocr_full_136_...`.
- `PIPELINE_V2_QUEUE` - Redis-очередь worker-а, по умолчанию `files:pipeline_v2`.
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_URL` - подключение к Redis.
- `SHARED_FILES_DIR` - путь к рабочему хранилищу внутри worker-контейнера.
- `PIPELINE_V2_MAX_PAGES` - ограничение количества страниц для отладки, `0` означает без ограничения.
- `PIPELINE_V2_FORCE_DOC_TYPE` - принудительный тип документа для диагностики.
- `LOG_LEVEL` - уровень логирования.
- `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `LANG=C.UTF-8`, `LC_ALL=C.UTF-8` - обязательные настройки, чтобы кириллица не превращалась в `????` или mojibake.

## Статика и качество

В проекте зафиксированы базовые quality gates:

- `ruff` для форматирования и линтинга.
- `pytest` для быстрого unit-контура без OCR.
- `mypy` для постепенного усиления типизации новых core/shared модулей.

Ресурсы и словари должны храниться в UTF-8, а не внутри случайных runtime-констант с ручной перекодировкой.

Пример локального `.env` хранится в:

- `shared/config/examples/.env.example`

Сам файл `.env` не должен попадать в git.

## Docker-запуск полного контура

Перед первым запуском убедиться, что локальные папки существуют:

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2
New-Item -ItemType Directory -Force Incoming, shared\files | Out-Null
```

Основной production-like запуск:

```powershell
docker compose up -d --build redis file-monitor worker-pipeline-v2 api ui-web
```

Открыть:

- Новый UI: `http://localhost:8080`
- API health: `http://localhost:8000/api/health`
- API stats: `http://localhost:8000/api/stats`

Чтобы обработать новый документ:

```powershell
Copy-Item "C:\path\to\document.pdf" .\Incoming\
```

После этого:

1. `file-monitor` увидит файл в `Incoming`.
2. Оригинал появится в `shared/files/<document>/original/`.
3. Задача уйдет в Redis-очередь `files:pipeline_v2`.
4. `worker-pipeline-v2` выполнит OCR и runtime pipeline.
5. Итоговый JSON появится в `shared/files/<document>/data/final_json/`.
6. UI покажет документ, поля, события и артефакты через API.

Если UI должен показывать именно live-документы верхнего уровня `shared/files`, задайте для API:

```powershell
$env:ALGOFUSION_RUN_ROOT="/shared/files"
docker compose up -d --build api ui-web
```

Если нужно смотреть зафиксированный benchmark-прогон на 136 документов, задайте конкретную папку:

```powershell
$env:ALGOFUSION_RUN_ROOT="/shared/files/_no_ocr_full_136_20260418_current_rerun4_waybill_fixes"
docker compose up -d --build api ui-web
```

## Перенос на другой ноутбук

Для переносимого локального запуска проект использует относительные пути внутри репозитория:

- `HOST_INCOMING_PATH=./Incoming`
- `HOST_SHARED_FILES_PATH=./shared/files`

Быстрая подготовка на новой машине:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_portable.ps1
docker compose up --build
```

`bootstrap_portable.ps1`:

- создает локальные папки `Incoming` и `shared/files`;
- копирует переносимый шаблон `.env`, если локальный `.env` еще не создан;
- оставляет проект готовым к локальному Docker-запуску без машинных путей вроде `C:\Users\...` или `/home/...`.

Для упаковки проекта в переносимый zip без `.git`, `.env`, `Incoming` и рабочих артефактов:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_portable_bundle.ps1
```

Скрипт создаст zip рядом с папкой репозитория.

Полный контур со всеми сервисами:

```powershell
docker compose up -d --build redis file-monitor worker-pipeline-v2 api ui-web
```

Основные сервисы:

- `redis` - очередь задач и статусы.
- `file-monitor` - наблюдение за входящей папкой.
- `worker-pipeline-v2` - обработка документов.
- `api` - данные для нового UI.
- `ui-web` - основной React UI на `8080`.
- `ui` - старый Streamlit fallback на `8501`, запускается только если он нужен отдельно.

Если Docker не может скачать базовый образ из Docker Hub из-за `TLS handshake timeout`, обычно это сетевая проблема Docker Hub/интернета. Повторный запуск часто помогает:

```powershell
docker compose up --build
```

## Быстрые проверки без OCR

Unit-тесты:

```powershell
python -m pytest -q -p no:cacheprovider
```

Компиляция модулей:

```powershell
python -m compileall -q workers/OCR-Sergei/PIPELINE_V2/src/modules tests
```

Эти проверки быстрые и не запускают OCR.

## Контрольная приемка версии

Минимальная проверка перед передачей:

```powershell
python -m pytest -q -p no:cacheprovider
cd ui-web
npm run build
cd ..
docker compose up -d --build redis file-monitor worker-pipeline-v2 api ui-web
docker compose ps
```

Ожидаемое состояние:

- `redis` healthy.
- `worker-pipeline-v2` healthy и слушает `files:pipeline_v2`.
- `api` healthy на `http://localhost:8000/api/health`.
- `ui-web` отвечает на `http://localhost:8080`.

Для быстрой регрессии без повторного OCR используется `scripts/run_pipeline_v2_precomputed_smoke.py` и подготовленные OCR/gold-артефакты. Текущий benchmark-набор для UI и проверки качества:

- run-root: `shared/files/_no_ocr_full_136_20260418_current_rerun4_waybill_fixes`;
- количество документов: `136`;
- типы: `waybill`, `invoice`, `payment_order`, `account_prot`;
- переносимые внешние артефакты: `C:\Users\Misha\Documents\AlgoFusion2_artifacts_136_20260418`, если папка присутствует на машине.

Если precomputed-набор не содержит `__waybill_header_ocr.json`, номер накладной может остаться `null` в проверке без OCR. В полном OCR-прогоне fallback-кроп формируется заново.

## Рабочие артефакты

Рабочая папка одного документа обычно содержит:

- `original/` - исходный файл.
- `cleaner/` - PNG после очистки.
- `ocr/` или OCR JSON-артефакты - сырой результат распознавания.
- `final_rebuilt_auto/` - промежуточные страницы и debug-артефакты сборки.
- `data/pred/` - предварительный JSON.
- `data/pred_normalized/` - нормализованный JSON.
- `data/pred_reconciled/` - JSON после сверки/досборки.
- `data/final_json/` - итоговый JSON.

`shared/files/` не хранится в git, потому что там появляются большие локальные PNG, PDF, JSON и debug-прогоны.

## Почему версия 2 устроена единым worker-ом

В текущей задаче качество важнее формального разделения на много маленьких worker-ов. Один worker держит рядом оригинал, очищенные PNG, OCR, структуру страниц, fallback-кропы и финальную сборку. Это дает практические преимущества:

- проще отладить документ от оригинала до финального JSON;
- меньше риск потерять контекст между стадиями;
- проще переиспользовать уже готовый OCR без повторного дорогого распознавания;
- легче локализовать проблему в конкретной странице, crop-зоне или item-строке;
- стабильнее работает document-level логика для многостраничных документов.

В будущем контур можно дробить на отдельные worker-и, но делать это стоит после стабилизации контрактов между стадиями.

## Правила сопровождения

- Не добавлять ручные подмены под конкретный документ без отдельного решения.
- Любая нормализация должна быть общей для типа документа или поля.
- Если восстановление поля не имеет надежных опор, использовать `проверить поле`.
- OCR не запускать в быстрых регрессионных проверках, если уже есть precomputed OCR JSON.
- Новую доменную логику выносить из `runtime.py` в отдельный тематический модуль.
- Для изменений в нормализации добавлять unit-тесты.
- Следить, чтобы все текстовые файлы сохранялись в UTF-8.
