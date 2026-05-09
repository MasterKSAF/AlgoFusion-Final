# AlgoFusion 2 UI

`ui-web/` - рабочий React/Vite интерфейс для текущего пайплайна AlgoFusion 2. Он не запускает OCR сам по себе, а показывает состояние актуального run-root из `shared/files`, итоговые JSON, проблемные поля, ручные review-правки и артефакты документов через FastAPI API из `api/`.

## Что входит

- `api/` - FastAPI-адаптер над `shared/files` и событиями Redis.
- `ui-web/` - вкладочный интерфейс оператора и разработчика с русскими смысловыми подписями полей, техническими путями, подсказками и светлой/тёмной темой.
- `docker-compose.yml` - сервисы `api` на `8000` и `ui-web` на `8080`.

## Вкладки

- `Обзор` - общие метрики, готовность набора, типы документов, быстрый список проблемных документов.
- `Документы` - таблица документов с поиском, фильтрами по типу/статусу и карточкой выбранного документа.
- `Проверка` - очередь документов, поля `null`/`review`/`invalid`, русское название поля над техническим path и ручные правки в `data/review_overrides/ui_review.json`.
- `Артефакты` - выбор документа, список JSON/PNG/PDF/TXT артефактов и preview выбранного файла.
- `События` - компактный технический журнал пайплайна/API и базовые счётчики.

## Поведение UI

- Кнопка `Тёмная тема` / `Светлая тема` переключает тему и сохраняет выбор в `localStorage`.
- Кружок `i` рядом с ключевыми заголовками показывает короткую подсказку по вкладке или действию.
- В `Документах` фильтры и правая карточка выбранного документа закреплены при прокрутке.
- В `Проверке` кнопка `Сохранить ручные правки` сохраняет override отдельно от исходного `final_json`.

Вкладки также открываются напрямую:

- `http://localhost:8080/#overview`
- `http://localhost:8080/#documents`
- `http://localhost:8080/#review`
- `http://localhost:8080/#artifacts`
- `http://localhost:8080/#events`

## Локальный запуск

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2
pip install -r api\requirements.txt
python -m uvicorn api.algofusion_api.main:app --host 127.0.0.1 --port 8000
```

Во втором терминале:

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2\ui-web
npm ci
npm run dev
```

Открыть:

- API health: `http://127.0.0.1:8000/api/health`
- UI dev: `http://127.0.0.1:5173`

## Docker

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2
docker compose up --build redis api ui-web
```

Открыть:

- UI: `http://localhost:8080`
- API health: `http://localhost:8000/api/health`
- API stats через UI proxy: `http://localhost:8080/api/stats`

## Данные

API читает run-root из `shared/files`. Для production/live-режима, когда документы приходят через `Incoming`, удобно показывать верхний уровень `/shared/files`:

```powershell
$env:ALGOFUSION_RUN_ROOT="/shared/files"
docker compose up -d --build api ui-web
```

Для benchmark-прогона можно зафиксировать конкретную папку:

```powershell
$env:ALGOFUSION_RUN_ROOT="/shared/files/_no_ocr_full_136_20260418_current_rerun4_waybill_fixes"
docker compose up -d --build api ui-web
```

Если `ALGOFUSION_RUN_ROOT` не задан, API ищет папку с максимальным количеством документных директорий и `data/final_json`.

## Проверка

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2\ui-web
npm run build
```

Smoke через Docker:

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2
docker compose up -d --build redis file-monitor worker-pipeline-v2 api ui-web
```

Ожидаемо:

- `GET http://localhost:8000/api/health` возвращает `ok: true`.
- `GET http://localhost:8080` возвращает HTML приложения.
- `GET http://localhost:8080/api/stats` возвращает метрики текущего run-root.
