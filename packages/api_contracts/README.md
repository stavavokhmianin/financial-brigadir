# api_contracts

`openapi.yaml` — единственный актуальный перечень эндпоинтов `/api/v1` (раздел 8.3 ТЗ).

- Источник истины — код FastAPI. Файл обновляется командой
  `python services/api/scripts/export_openapi.py`.
- Тест `services/api/tests/test_openapi_contract.py` падает, если файл разошёлся с кодом.
- Клиент генерирует из файла TypeScript-типы (`apps/client`, `npm run gen:api`).
