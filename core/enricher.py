"""
enricher.py — İş ilanına göre pool'u zenginleştirir (in-memory).
Eksik becerileri ÖNERİR (kullanıcı onaylar), açıklamaları pozisyona uygun güçlendirir.
Pool dosyalarını DEĞİŞTİRMEZ; bellekte çalışır.
"""

import copy
import json
from openai import OpenAI

LEVEL_MAP = {
    1: "beginner",
    2: "beginner",
    3: "intermediate",
    4: "advanced",
    5: "advanced",
}


def analyze(pool: dict, job_text: str, model: str, api_key: str) -> dict:
    """
    LLM ile ilanı analiz eder, eksik skill önerileri ve açıklama revizyonları döndürür.
    Henüz pool'a bir şey YAZMAZ — sadece ham LLM sonucunu döndürür.
    """
    current_skills = []
    for group in ["technical", "ai_ml", "tools"]:
        for s in pool.get("skills", {}).get(group, []):
            current_skills.append(s["name"])

    experiences = pool.get("experience", [])
    projects = pool.get("projects", [])

    prompt = f"""You are a senior CV optimization expert.
Given the job posting and the candidate's current CV data below, perform two tasks:

TASK 1 — SKILL GAP ANALYSIS
Identify technologies, skills, or tools required by the job posting that are NOT already
in the candidate's skill list. For each missing skill, return:
- "name": skill name (concise, e.g. "Neo4j", "GraphRAG", "FastAPI")
- "group": one of "technical", "ai_ml", or "tools"
- "tags": relevant lowercase tags array
- "reason": why the job requires this (one short sentence)

Do NOT duplicate skills already in the list.

Current skills: {json.dumps(current_skills, ensure_ascii=False)}

TASK 2 — DESCRIPTION REVISION
Rewrite each experience and project description to better emphasize aspects relevant
to the target job posting.
Rules:
- Do NOT invent new responsibilities or technologies not implied by the original
- Reframe and elaborate existing content to highlight matching keywords from the job
- Keep descriptions concise (2-4 sentences max)
- Use professional English
- Every experience and project must be returned (even if unchanged)

JOB POSTING:
{job_text}

CURRENT EXPERIENCES:
{json.dumps(experiences, ensure_ascii=False, indent=2)}

CURRENT PROJECTS:
{json.dumps(projects, ensure_ascii=False, indent=2)}

Return ONLY a valid JSON object with this exact structure:
{{
  "suggested_skills": [
    {{ "name": "...", "group": "...", "tags": ["..."], "reason": "..." }}
  ],
  "updated_experiences": [
    {{ "id": "exp_001", "description": "revised description" }}
  ],
  "updated_projects": [
    {{ "id": "proj_001", "description": "revised description" }}
  ]
}}

Return ONLY valid JSON, no markdown fences, no explanation.
"""

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

    result = json.loads(raw)
    if isinstance(result, dict) and "suggested_skills" not in result:
        for v in result.values():
            if isinstance(v, dict) and "suggested_skills" in v:
                result = v
                break

    return result


def apply_enrichment(pool: dict, approved_skills: list[dict],
                     analysis: dict) -> tuple[dict, dict]:
    """
    Kullanıcı tarafından onaylanan skill'leri ve açıklama revizyonlarını pool'a uygular.
    Returns: (enriched_pool, report)
    """
    enriched = copy.deepcopy(pool)

    # ── Onaylanan skill'leri ekle ──
    added_skills = []
    for skill in approved_skills:
        group = skill["group"]
        if group not in enriched.get("skills", {}):
            enriched["skills"][group] = []
        existing_names = {s["name"].lower() for s in enriched["skills"][group]}
        if skill["name"].lower() not in existing_names:
            enriched["skills"][group].append({
                "name": skill["name"],
                "level": skill["level"],
                "tags": skill.get("tags", []),
            })
            added_skills.append(f"{skill['name']} ({skill['level']}, {group})")

    # ── Experience açıklamalarını güncelle ──
    exp_updates = {u["id"]: u["description"]
                   for u in analysis.get("updated_experiences", [])}
    revised_exps = []
    for exp in enriched.get("experience", []):
        if exp["id"] in exp_updates and exp_updates[exp["id"]] != exp["description"]:
            exp["description"] = exp_updates[exp["id"]]
            revised_exps.append(exp["id"])

    # ── Proje açıklamalarını güncelle ──
    proj_updates = {u["id"]: u["description"]
                    for u in analysis.get("updated_projects", [])}
    revised_projs = []
    for proj in enriched.get("projects", []):
        if proj["id"] in proj_updates and proj_updates[proj["id"]] != proj["description"]:
            proj["description"] = proj_updates[proj["id"]]
            revised_projs.append(proj["id"])

    report = {
        "added_skills": added_skills,
        "revised_experiences": revised_exps,
        "revised_projects": revised_projs,
    }

    return enriched, report
