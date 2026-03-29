"""
selector.py — LLM ile havuz kalemlerini iş ilanına göre seçer.
Her kalem için include: true/false kararı döndürür.
"""

import json
import os
from pathlib import Path
from openai import OpenAI

POOL_DIR = Path(__file__).parent.parent / "pool"


def load_pool() -> dict:
    pool = {}
    for file in POOL_DIR.glob("*.json"):
        with open(file, encoding="utf-8") as f:
            pool[file.stem] = json.load(f)
    return pool


def _skill_id(name: str) -> str:
    return f"skill_{name.lower().replace(' ', '_').replace('/', '_')}"


def _flatten_items(pool: dict) -> list[dict]:
    items = []

    for section in ["experience", "education", "projects", "certifications"]:
        for item in pool.get(section, []):
            items.append({"section": section, **item})

    skills = pool.get("skills", {})
    for group in ["technical", "ai_ml", "tools"]:
        for skill in skills.get(group, []):
            items.append({
                "section": "skills",
                "group": group,
                "id": _skill_id(skill["name"]),
                **skill,
            })

    return items


def run(pool: dict, job_text: str, model: str, api_key: str) -> dict:
    """
    Havuz kalemlerini LLM ile filtreler.
    Döndürür: { "id": bool, ... }
    """
    items = _flatten_items(pool)

    # Personal her zaman dahil — LLM'e sorma
    decisions = {"personal": True}

    prompt = f"""You are a senior technical recruiter and CV expert.
Evaluate the CV pool items below for the given job posting.

For each item return a JSON array with this exact format:
{{ "id": "<item_id>", "include": true | false, "reason": "<one sentence>" }}

Rules:
- Include items that directly match the job requirements or strongly support the application
- Exclude items clearly unrelated to the role
- Keep the total CV to maximum 2 pages (be selective with projects and certificates)
- Always include all education entries
- For skills: include only skills relevant to the job

JOB POSTING:
{job_text}

CV POOL ITEMS:
{json.dumps(items, ensure_ascii=False, indent=2)}

Return ONLY a valid JSON array, no markdown, no explanation.
"""

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content

    # Markdown code block varsa soy (```json ... ``` veya ``` ... ```)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]          # ilk ``` sonrası
        if raw.startswith("json"):
            raw = raw[4:]                      # "json" etiketini at
        raw = raw.rsplit("```", 1)[0]          # kapanan ``` öncesi
        raw = raw.strip()

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = next((v for v in parsed.values() if isinstance(v, list)), [])

    for entry in parsed:
        decisions[entry["id"]] = entry["include"]

    return decisions, parsed  # decisions: id→bool, parsed: detaylı liste


def filter_pool(pool: dict, decisions: dict) -> dict:
    """decisions'a göre pool'u filtreler, seçilenleri döndürür."""
    selected = {"personal": pool["personal"]}

    for section in ["experience", "education", "projects", "certifications"]:
        selected[section] = [
            item for item in pool.get(section, [])
            if decisions.get(item["id"], False)
        ]

    skills = pool.get("skills", {})
    selected["skills"] = {
        "languages": skills.get("languages", [])
    }
    for group in ["technical", "ai_ml", "tools"]:
        selected["skills"][group] = [
            s for s in skills.get(group, [])
            if decisions.get(_skill_id(s["name"]), False)
        ]

    return selected
