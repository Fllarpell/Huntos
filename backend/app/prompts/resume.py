PARSE_SYSTEM = """You are Huntos AI, an ATS-bypass engine. NO fluff words. Return valid JSON only.
Extract the source resume into the rigid schema. Do not invent employers, dates, degrees, or skills that are not in the text.
Keep bullet wording close to the original. Use the source language (Russian or English). Empty string or [] if unknown."""

PARSE_USER = """Source resume text:
---
{text}
---

Return JSON with exactly these keys:
{{
  "name": "",
  "headline": "",
  "email": "",
  "phone": "",
  "telegram": "",
  "location": "",
  "links": ["https://..."],
  "summary": "",
  "about_items": [{{"label": "", "text": ""}}],
  "skills": ["FastAPI"],
  "skill_groups": [{{"label": "Python", "items": "FastAPI, AsyncIO"}}],
  "experience": [
    {{
      "company": "",
      "title": "",
      "period": "",
      "context": "",
      "bullets": [{{"text": "", "children": []}}]
    }}
  ],
  "education": [{{"school": "", "degree": "", "period": "", "bullets": []}}],
  "languages": [],
  "courses": [],
  "hackathons": []
}}
"""
