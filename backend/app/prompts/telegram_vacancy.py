EXTRACT_SYSTEM = """Ты разбираешь пост из Telegram-канала с вакансиями.
Отвечай ТОЛЬКО валидным JSON без markdown.
Если это не вакансия (реклама, новость, опрос, пересылка без роли) — is_vacancy=false.
Не выдумывай контакты и зарплату, которых нет в тексте."""

EXTRACT_USER = """Канал: @{channel}
Дата: {date}

Пост:
---
{text}
---

Верни JSON:
{{
  "is_vacancy": true или false,
  "title": "должность или короткая суть",
  "company": "компания или NDA если скрыта, иначе null",
  "grade": "intern|junior|middle|senior|lead|head или null",
  "work_format": "удалённо|офис|гибрид или null",
  "location": "город/страна или null",
  "salary_raw": "как в посте или null",
  "telegram_alias": "username для связи без @, или null",
  "skills": ["навыки из поста"],
  "requirements": "требования сплошным текстом",
  "description": "остальное: задачи, условия"
}}
"""
