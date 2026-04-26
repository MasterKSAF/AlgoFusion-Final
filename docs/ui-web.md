# Algofusion UI Web

Новый production-style интерфейс лежит в `ui-web/` и работает через HTTP API из `api/`.
Старый Streamlit UI в `ui/` пока оставлен как fallback.

## Что входит

- `api/` - FastAPI-адаптер над `shared/files` и Redis events.
- `ui-web/` - React/Vite интерфейс в стиле операционной панели из демо.
- `docker-compose.yml` - добавлены сервисы `api` на порту `8000` и `ui-web` на порту `8080`.

## Локальный запуск

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2
pip install -r api\requirements.txt
python -m uvicorn api.algofusion_api.main:app --host 127.0.0.1 --port 8000
```

Во втором терминале:

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2\ui-web
npm install
npm run dev
```

Открыть:

- API health: `http://127.0.0.1:8000/api/health`
- UI dev: `http://127.0.0.1:5173`

## Docker

```powershell
cd C:\Users\Misha\Documents\GitHub\AlgoFusion2
docker compose up --build api ui-web
```

Открыть:

- Новый UI: `http://localhost:8080`
- API: `http://localhost:8000/api/health`

## Данные

API автоматически выбирает самый полный run-root внутри `shared/files`.
Для явного выбора можно задать:

```powershell
$env:ALGOFUSION_RUN_ROOT="C:\Users\Misha\Documents\GitHub\AlgoFusion2\shared\files\_no_ocr_full_136_20260418_current_rerun4_waybill_fixes"
```

Если `ALGOFUSION_RUN_ROOT` не задан, API ищет папку с максимальным количеством документных директорий и `data/final_json`.

## Экраны

- `Мониторинг` - общие счетчики, список документов, статусы, прогресс, события.
- `Экспорт 1С` - очередь документов, проблемные поля `null`/`проверить поле`, черновое сохранение ручных правок.
- `Developer Explorer` - дерево артефактов, preview JSON/TXT/PNG/PDF.

Черновики правок UI сохраняются отдельно в `data/review_overrides/ui_review.json` и не перезаписывают `data/final_json`.

