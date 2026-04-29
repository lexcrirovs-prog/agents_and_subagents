# agents_and_subagents

Переносимый контур для команды агентов: директор получает задачу от
пользователя, делегирует ее отделам-субагентам, а отделы решают вопросы между
собой и возвращают директору уже собранный результат.

Проект построен на `ductor`: Telegram-first runtime, локальные CLI-провайдеры
Codex/Claude/Gemini, фоновые задачи, cron, webhooks и inter-agent bus.

## Состав команды

- `main` - директор, главный агент и финальный интегратор
- `marketing` - отдел маркетинга, стиль Telegram/MAX/YouTube/сайта и публикации
- `legal` - юрист, договоры, ГК РФ и интересы организации
- `technical-director` - технический директор, NotebookLM/RAG, нормативка и котлы
- `production` - производство, этапы, склад, скорость и узкие места
- `sales-lead` - руководитель продаж, звонки Билайн, транскрибация и скрипты

## Быстрый старт

```bash
python3 scripts/subscriber_install.py
python3 scripts/render_agent_templates.py
```

После установки:

1. Скопируйте `runtime-template/agents.example.json` в
   `runtime-template/agents.json`.
2. Заполните `allowed_user_ids` для каждого субагента.
3. Заполните токены ботов в `runtime-template/.env`.
4. Перезапустите runtime.

## Источники данных

Шаблон не содержит личных данных и токенов. Подключаемые источники описаны в
`client-files/data-sources.example.json`:

- Telegram/MAX exports или API
- YouTube transcript/export
- выгрузка сайта или CMS
- NotebookLM/RAG экспорт для технической базы
- файл состояния производства котлов
- Beeline call export
- локальный путь к `transkrib_prog`

## Ключевые папки

- `agent-templates/` - манифест ролей субагентов
- `skills-generic/` - навыки отделов
- `shared-generic/team/` - правила взаимодействия и отчетности
- `project-vault-generic/` - архитектура и карточки ролей
- `runtime-template/` - готовый шаблон локального runtime
- `client-files/` - примеры структур файлов и подключений
- `ductor/` - vendored runtime framework

## Главный принцип

Субагент не должен возвращать директору сырой вопрос, если его может решить
другой отдел. Он консультируется с нужным субагентом, собирает общий вывод и
только потом возвращает директору статус `DONE`, `PARTIAL` или `BLOCKED`.
