# Docs

## Основной маршрут

- Начните с [`HANDOFF.md`](HANDOFF.md), если нужно принять проект и продолжить
  реализацию без старого контекста.
- Начните с [`ENTERPRISE_AGENTS.md`](ENTERPRISE_AGENTS.md), чтобы понять роли и
  поток делегирования.
- Запустите `python3 scripts/subscriber_install.py` из корня репозитория.
- Сгенерируйте отделы: `python3 scripts/render_agent_templates.py`.
- Используйте [`../runtime-template/README.md`](../runtime-template/README.md)
  для layout runtime и maintenance-команд.
- Используйте [`VALIDATION_MATRIX.md`](VALIDATION_MATRIX.md) для проверки.
- Правьте [`../agent-templates/team.example.json`](../agent-templates/team.example.json),
  если меняется состав отделов.

## Важные границы

- В репозитории нет токенов, личных архивов, звонков, договоров или чатов.
- Реальные источники подключаются через `.env`, exports или файлы в
  `client-files/`.
- Публикации, отправка сообщений, выгрузка звонков и юридически значимые
  действия требуют явного разрешения оператора.
