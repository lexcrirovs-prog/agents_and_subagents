# antibiotik-open

Чистый, переносимый контур для подписчиков и клиентов.

Это отдельный проект рядом с исходным private-contour.
Его задача — собрать обезличенную, устанавливаемую multi-agent систему без
личных данных исходного оператора, без семейного контекста и без живых
зависимостей на приватный operational contour.

## Базовые правила

- исходный private-contour остаётся нетронутым;
- этот проект живёт в отдельной директории и не использует private-runtime
  как live dependency;
- переносим только generic architecture, generic skills и чистые runtime
  шаблоны;
- пользовательские и семейные данные, токены, архивы, логи, daily notes и
  личные knowledge packs сюда не переносятся.

## Быстрый старт

Основной install path теперь один:

```bash
python3 scripts/subscriber_install.py
```

Инсталлер сам:

- поднимает `.venv` и ставит зависимости;
- обновляет public-safe runtime template;
- определяет локальную авторизацию Codex / Claude;
- запрашивает токен Telegram-бота;
- привязывает реальный `owner user id` через одноразовую команду `/pair`;
- записывает `.env` и `config/config.json`;
- гоняет strict preflight;
- поднимает runtime, если не указан `--no-start`.

Платформенный таргет для v1:

- macOS: основной путь;
- Linux / Linux server: основной путь;
- Windows: честный baseline сейчас через WSL2, native parity не обещаем до
  отдельной проверки wrapper/service contour.

## Архивный артефакт

Чтобы собрать отдельную папку для раздачи подписчикам:

```bash
python3 scripts/build_subscriber_kit.py
```

Чтобы сразу получить и папку, и zip-архив:

```bash
python3 scripts/build_subscriber_kit.py --zip
```

Готовый артефакт появляется в:

`dist/subscriber-kit`

Архив появляется в:

`dist/subscriber-kit.zip`

Эту папку уже можно архивировать отдельно от рабочего repo-контура.

## Структура

- `docs/README.md` — краткий вход в документацию для handoff/install
- `docs/internal/` — внутренние engineering notes, не обязательные клиенту
- `runtime-template/` — чистый шаблон runtime для будущих инсталляций
- `skills-generic/` — только обезличенные reusable skills
- `client-files/` — место для клиентских файлов и примеров структуры, не для
  личных данных оператора

## Текущее состояние

- v1 handoff contour собран;
- privacy-критичные следы и host-derived runtime leftovers вычищены;
- installer-first install flow собран вокруг `scripts/subscriber_install.py`;
- generic team/shared, context hygiene и project-vault seed включены в runtime
  template;
- internal engineering notes отделены от клиентского install path.
