"""
cover_letter.py — Seçilen kalemler + iş ilanından niyet mektubu üretir.
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def generate(selected: dict, job_text: str, role: str, company: str,
             lang: str, model: str, api_key: str) -> str:

    name = selected["personal"]["name"]

    exp_lines = [
        f"- {e['title']} at {e['company']}: {e['description'][:150]}"
        for e in selected.get("experience", [])[:3]
    ]
    proj_lines = [
        f"- {p['title']}: {p['description'][:150]}"
        for p in selected.get("projects", [])[:2]
    ]
    highlights = "\n".join(exp_lines + proj_lines)

    lang_instruction = "Write in English." if lang == "en" else "Türkçe yaz."

    prompt = f"""Write a professional cover letter for a job application.
{lang_instruction}

Structure — 3 paragraphs:
1. Why this specific role and company (show you've read the posting)
2. Prove fit using 2-3 of the highlighted experiences/projects below
3. Forward-looking: what you'll contribute, call to action

Tone: professional, direct, genuinely enthusiastic — not generic.
Length: ~250 words total.
Sign off with: {name}

APPLICANT: {name}
TARGET ROLE: {role} at {company}

JOB POSTING:
{job_text}

SELECTED HIGHLIGHTS:
{highlights}

Return ONLY the letter body (no "Subject:" line, no address block), starting from the opening paragraph.
"""

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )

    letter_text = response.choices[0].message.content.strip()

    # HTML'e render et
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("cover_letter.html")
    html = template.render(
        personal=selected["personal"],
        role=role,
        company=company,
        body=letter_text,
    )
    return html
