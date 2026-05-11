# Итоговое задание — тестирование F-Bank

Репозиторий содержит:
- ручные тест-кейсы (5 шт.);
- баг-репорты (2 разных дефекта);
- автотесты Selenium на найденные дефекты;
- CI GitHub Actions, который запускает Selenium-тесты и падает на дефектах (красная сборка).

## Структура
- `docs/manual-tests.md` — 5 ручных тестов
- `docs/bugreports/BUG-001.md` — дефект длины номера карты
- `docs/bugreports/BUG-002.md` — дефект отрицательного перевода
- `tests/test_defects.py` — автотесты на дефекты
- `.github/workflows/selenium.yml` — CI
- `.github/ISSUE_TEMPLATE/bug_001_card_number_17_digits.md` — шаблон GitHub Issue для BUG-001
- `.github/ISSUE_TEMPLATE/bug_002_negative_transfer.md` — шаблон GitHub Issue для BUG-002
- `docs/github-issues.md` — инструкция по заведению багов в GitHub Issues

## Локальный запуск тестов
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```
