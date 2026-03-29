# CV Manager

> AI-powered CV generator that tailors your resume to each job posting — automatically.

---

## What It Does

CV Manager keeps all your experience, skills, projects, and certifications in a **JSON pool**. When you provide a job listing, the LLM:

1. **Enriches** your pool — rewrites descriptions to highlight relevant keywords
2. **Selects** which items to include — based on the job requirements
3. **Writes** a custom *About Me* paragraph from scratch
4. **Renders** everything into a clean PDF via Jinja2 + WeasyPrint
5. *(Optional)* Generates a **cover letter** tailored to the position

One command → one ready-to-send PDF.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up your API key

Copy `.env.example` to `.env` and add your key:

```bash
cp .env.example .env
```

```env
OPENROUTER_API_KEY=your_key_here
```

### 3. Fill your pool

Edit the files inside `pool/` with your real data:

| File | Content |
|------|---------|
| `personal.json` | Name, contact info, social links |
| `experience.json` | Work & internship history |
| `education.json` | Degrees and schools |
| `projects.json` | Projects with tags |
| `skills.json` | Technical skills grouped by category |
| `certifications.json` | Certificates |

### 4. Add a job listing

Paste the raw job description into a `.txt` file inside `jobs/`:

```bash
jobs/google_ml_engineer.txt
```

### 5. Generate your CV

```bash
python main.py generate \
  --job jobs/google_ml_engineer.txt \
  --company Google \
  --role "ML Engineer" \
  --lang en
```

Output is saved to:

```
outputs/Google_2026-03-29/
├── cv.pdf
└── cover_letter.pdf   # if --cover-letter flag used
```

---

## Project Structure

```
cv_manager/
├── pool/               # Your data (fill once, reuse forever)
├── jobs/               # Raw job description text files
├── templates/          # Jinja2 HTML templates for CV & cover letter
├── outputs/            # Generated PDFs
├── core/
│   ├── enricher.py     # LLM — rewrites pool items for the job
│   ├── selector.py     # LLM — picks which items to include
│   ├── builder.py      # Renders HTML from selected items
│   ├── pdf_exporter.py # HTML → PDF via WeasyPrint
│   └── cover_letter.py # LLM — generates cover letter
├── main.py             # CLI entry point
├── config.yaml         # Model, language, template settings
└── requirements.txt
```

---

## Configuration

Edit `config.yaml` to change the model, language, or output settings:

```yaml
llm:
  provider: openrouter
  model: google/gemini-3.1-flash-lite-preview

lang: en          # en | tr
max_cv_pages: 2
```

---

## Cover Letter

Add `--cover-letter` to also generate a cover letter:

```bash
python main.py generate --job jobs/x.txt --company Stripe --role "Backend Engineer" --cover-letter
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| LLM | OpenRouter (configurable model) |
| Templates | Jinja2 + HTML/CSS |
| PDF | WeasyPrint |
| CLI | Typer |
| Data | JSON (pool) + YAML (config) |

---

## Roadmap

- [x] Pool JSON files (experience, projects, skills, certs)
- [x] LLM enricher, selector, builder, PDF export
- [x] Cover letter generation
- [ ] CLI approval screen with override support
- [ ] ATS score — keyword overlap analysis
- [ ] Job URL → auto scraping
- [ ] Streamlit web interface
- [ ] Application history tracker

---

## License

MIT
