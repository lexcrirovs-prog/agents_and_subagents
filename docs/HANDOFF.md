# Project Handoff

Дата: 2026-04-30  
Репозиторий: https://github.com/lexcrirovs-prog/agents_and_subagents  
Локальный путь: `C:\Users\lexcr\Downloads\Telegram Desktop\antibiotik-subscriber-kit-fixed\subscriber-kit`

## Цель проекта

Проект реализует Telegram-first систему агентов на базе `ductor`.

Схема:

```text
Пользователь -> main / Директор -> профильный субагент
                                  -> другой субагент при необходимости
                                  <- сводный ответ профильного субагента
Пользователь <- main / Директор
```

Главный принцип: субагент не возвращает директору сырой вопрос, если вопрос
может решить другой отдел. Он консультируется с нужным субагентом, собирает
общий вывод и возвращает директору статус `DONE`, `PARTIAL` или `BLOCKED`.

## Текущее состояние

Готово:

- проект загружен в GitHub;
- локальная папка стала git-репозиторием и отслеживает `origin/main`;
- добавлен директор `main`;
- добавлены 5 субагентов-отделов;
- добавлены skills для отделов;
- добавлены правила handoff между отделами;
- добавлены шаблоны источников данных;
- сгенерирован `runtime-template/agents.example.json`;
- проверены генераторы и сборка handoff-артефакта.

Последняя проверенная команда публикации:

```bash
git push -u origin main
```

Последний известный коммит базовой реализации:

```text
e82eaa0 Adapt enterprise agent team
```

## Состав команды

| Agent | Роль | Зона ответственности |
| --- | --- | --- |
| `main` | Директор | принимает задачи, делегирует, интегрирует результат |
| `marketing` | Отдел маркетинга | стиль Telegram/MAX/YouTube/сайта, посты, расписание |
| `legal` | Юрист | договоры, ГК РФ, риски и интересы организации |
| `technical-director` | Технический директор | NotebookLM/RAG, нормативка, котлы, комплектации, сдача объектов |
| `production` | Производство | статус производства, этапы, склад, узкие места |
| `sales-lead` | Руководитель отдела продаж | звонки Билайн, транскрибация, оценка по скриптам |

## Ключевые файлы

```text
README.md
docs/ENTERPRISE_AGENTS.md
docs/VALIDATION_MATRIX.md
agent-templates/team.example.json
runtime-template/agents.example.json
runtime-template/.env.example
runtime-template/workspace/AGENTS.md
runtime-template/shared/team/AgentRoster.md
runtime-template/shared/team/HandoffPlaybook.md
runtime-template/workspace/memory_system/profile/SkillRoster.md
skills-generic/
client-files/data-sources.example.json
project-vault-generic/
```

## Что уже проверено

Из корня проекта выполнялись:

```powershell
python scripts\sync_runtime_template.py
python scripts\render_agent_templates.py
python scripts\subscriber_install.py --help
python scripts\build_subscriber_kit.py
python -m py_compile scripts\sync_runtime_template.py scripts\render_agent_templates.py scripts\build_subscriber_kit.py
```

Проверочный `dist/` после сборки удален и добавлен в `.gitignore`.

## Что нужно сделать пользователю дальше

### 1. Создать Telegram-ботов

В `@BotFather` создать 6 ботов:

1. директор;
2. маркетинг;
3. юрист;
4. технический директор;
5. производство;
6. руководитель продаж.

Токены не коммитить в GitHub.

### 2. Установить runtime

```powershell
python scripts\subscriber_install.py
```

Установщик попросит токен директора и сделает Telegram-pairing через `/pair`.

### 3. Создать `agents.json`

```powershell
Copy-Item runtime-template\agents.example.json runtime-template\agents.json
```

В `runtime-template\agents.json` заполнить `allowed_user_ids` для каждого
субагента.

### 4. Заполнить `.env`

```powershell
Copy-Item runtime-template\.env.example runtime-template\.env
```

Заполнить:

```env
DUCTOR_TELEGRAM_TOKEN=
DUCTOR_AGENT_MARKETING_TELEGRAM_TOKEN=
DUCTOR_AGENT_LEGAL_TELEGRAM_TOKEN=
DUCTOR_AGENT_TECHNICAL_DIRECTOR_TELEGRAM_TOKEN=
DUCTOR_AGENT_PRODUCTION_TELEGRAM_TOKEN=
DUCTOR_AGENT_SALES_LEAD_TELEGRAM_TOKEN=
```

### 5. Перезапустить runtime

На Windows предпочтительно через WSL2:

```bash
python3 scripts/subscriber_install.py
python3 scripts/render_agent_templates.py
bash scripts/run-main.sh
```

### 6. Проверить делегирование

В Telegram написать директору:

```text
Кто входит в твою команду?
```

Потом проверить межагентное взаимодействие:

```text
Пусть маркетинг подготовит пост о паровых котлах и согласует технические формулировки с техническим директором.
```

Ожидаемый результат: директор делегирует `marketing`, `marketing` спрашивает
`technical-director`, затем возвращает директору сводный ответ.

## Источники данных, которые еще нужно подключить

Шаблоны лежат в `client-files/`.

Минимальные реальные источники:

- Telegram export или API для маркетинга;
- MAX export или API для маркетинга;
- YouTube transcripts/export;
- выгрузка сайта или CMS;
- договоры и политика интересов организации;
- NotebookLM/RAG export или локальная техническая база;
- нормативные документы;
- переписка с конструкторами;
- файл состояния производства котлов;
- выгрузки звонков Билайн;
- локальный путь к `transkrib_prog`;
- актуальные скрипты отдела продаж.

Важно: агенты должны называть отсутствующие источники, а не придумывать факты.

## Recurring jobs

Регулярные задачи добавлять после проверки базового inter-agent flow.

Типовые задачи:

- `marketing`: подготовка постов и расписания;
- `sales-lead`: ежедневная выгрузка звонков, транскрибация, отчет по скриптам;
- `production`: ежедневный анализ узких мест по файлу состояния.

Инструменты:

```text
runtime-template/workspace/tools/cron_tools/
```

## Ограничения и риски

- В репозитории нет реальных токенов и реальных клиентских данных.
- Реальная отправка сообщений, публикация постов, выгрузка звонков и отправка
  договорных правок требуют явного разрешения.
- NotebookLM может не иметь прямого локального API в этом контуре, поэтому
  базовый путь: экспорт документов или отдельный RAG-коннектор.
- Native Windows пока не основной путь; надежнее использовать WSL2.
- Юридический агент дает risk review и черновики правок, но не заменяет
  финальную проверку живым юристом.

## Следующий лучший шаг

Сначала поднять Telegram-директора и проверить обычный ответ. Затем подключить
одного субагента, например `legal`, и проверить `ask_agent.py`. Только после
этого подключать все пять отделов и регулярные задачи.
