"""
builder.py — Seçilen havuz kalemlerinden HTML CV üretir.
About paragrafını da LLM ile yazar.
"""

import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def generate_about(selected: dict, job_text: str, role: str, company: str,
                   lang: str, model: str, api_key: str) -> str:
    """Seçilen kalemlerden pozisyona özel About paragrafı üretir."""

    summary_parts = []
    for exp in selected.get("experience", [])[:3]:
        summary_parts.append(f"- {exp['title']} at {exp['company']}: {exp['description'][:120]}")
    for proj in selected.get("projects", [])[:3]:
        summary_parts.append(f"- Project '{proj['title']}': {proj['description'][:120]}")

    selected_summary = "\n".join(summary_parts)

    lang_instruction = "Write in English." if lang == "en" else "Türkçe yaz."

    prompt = f"""Write a professional 'About Me' paragraph for a CV.
{lang_instruction}
- 3-4 sentences, first person, confident but not exaggerated
- Highlight the 2-3 skills/experiences most relevant to the target role
- Do NOT list everything — be selective and sharp
- No generic filler phrases

TARGET ROLE: {role} at {company}

SELECTED HIGHLIGHTS:
{selected_summary}

JOB POSTING EXCERPT:
{job_text[:800]}

Return ONLY the paragraph text, no quotes, no labels.
"""

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()


def build_html(selected: dict, about: str, template_name: str = "cv.html") -> str:
    """Seçilen kalemler + about ile HTML string döndürür."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template(template_name)

    html = template.render(
        personal=selected["personal"],
        about=about,
        experience=selected.get("experience", []),
        education=selected.get("education", []),
        skills=selected.get("skills", {}),
        projects=selected.get("projects", []),
        certifications=selected.get("certifications", []),
    )
    return html
