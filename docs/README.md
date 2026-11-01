# Документация

Документы разделены по назначению. Актуальное состояние кода и команды запуска находятся
в корневом [README](../README.md); поэтапные отчёты в репозитории не хранятся.

## Продукт и UX

- [product-ux.md](product-ux.md) — принятая информационная архитектура и пользовательские
  сценарии.
- [learning-service-concept.md](learning-service-concept.md) — цикл обучения на операциях и
  обратной связи.
- [roadmap.md](roadmap.md) — проверяемый порядок развития после демо.
- [plans.md](plans.md) и [business-model.md](business-model.md) — тарифная логика и
  плановая экономика.
- [demo-script.md](demo-script.md) и [pitch/deck.md](pitch/deck.md) — материалы показа.
- [research/](research/) — гайд, пустой журнал интервью и проверка рынка.

## Расчёты, данные и SDK

- [sdk.md](sdk.md) — публичная граница самостоятельного SDK и примеры.
- [forecast-model.md](forecast-model.md) — правила расчёта и ограничения моделей.
- [backtest/baseline.md](backtest/baseline.md) — воспроизводимый синтетический бэктест.
- [data-model.md](data-model.md) — сущности и инварианты хранения.
- [csv-import.md](csv-import.md), [bank-mock.md](bank-mock.md) — источники данных.
- [alerts-policy.md](alerts-policy.md) — правила предупреждений и подавления повторов.
- [ADR/](ADR/) — принятые архитектурные решения.

## Эксплуатация, качество и безопасность

- [stand.md](stand.md) — публичный синтетический стенд.
- [pilot.md](pilot.md) — изолированный пилотный/on-prem-профиль.
- [quality-gates.md](quality-gates.md) — автоматическая приёмка и честные ограничения.
- [mobile-verification.md](mobile-verification.md) — Android/iOS build и device QA.
- [privacy.md](privacy.md) — экспорт, удаление и сроки хранения.
- [security-readiness.md](security-readiness.md) — что защищено фактически и что блокирует
  реальные финансовые данные.
- [threat-model.md](threat-model.md) — угрозы, меры и остаточные риски.

## Правила актуальности

- Документация описывает текущее поведение или явно помечается как план.
- Результаты CI и локальные скриншоты хранятся как временные artifacts, а не коммитятся.
- Историю решений сохраняют ADR и Git; отдельные отчёты по каждому этапу не создаются.
- Численные заявления должны ссылаться на воспроизводимый тест, скрипт или бэктест.
