"""
main.py — CV Manager CLI
Kullanım: python main.py generate --job jobs/x.txt --company Acme --role "ML Engineer"
"""

import json
import os
from datetime import datetime
from pathlib import Path

import typer
import yaml
from dotenv import load_dotenv

from core import enricher, selector, builder, cover_letter, pdf_exporter

load_dotenv()

app = typer.Typer(help="CV Manager — pozisyona özel CV ve niyet mektubu üretir.")
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def prompt_skill_approval(suggestions: list[dict]) -> list[dict]:
    """
    Her önerilen skill için kullanıcıya sorar:
      0 = ekleme, 1-5 = ekle (seviye)
    Onaylananları level bilgisiyle döndürür.
    """
    if not suggestions:
        typer.echo("\n    Eksik beceri bulunamadi.")
        return []

    typer.echo(f"\n-- Onerilen Beceriler ({len(suggestions)}) " + "-" * 20)
    typer.echo("    Her beceri icin seviye girin:")
    typer.echo("    0 = ekleme  |  1-2 = beginner  |  3 = intermediate  |  4-5 = advanced\n")

    approved = []
    for skill in suggestions:
        reason = skill.get("reason", "")
        label = f"  {skill['name']} ({skill['group']})"
        if reason:
            label += f"  — {reason}"
        typer.echo(label)

        while True:
            raw = typer.prompt(f"    Seviye [0-5]", default="0")
            try:
                level = int(raw)
                if 0 <= level <= 5:
                    break
            except ValueError:
                pass
            typer.echo("    ! 0-5 arasi bir sayi girin.")

        if level == 0:
            typer.echo("    -> atlanid")
            continue

        level_name = enricher.LEVEL_MAP[level]
        approved.append({
            "name": skill["name"],
            "group": skill["group"],
            "level": level_name,
            "tags": skill.get("tags", []),
        })
        typer.echo(f"    -> eklendi ({level_name})")

    typer.echo("-" * 47)
    return approved


def show_enrichment(report: dict) -> None:
    typer.echo("\n-- Zenginlestirme Sonucu " + "-" * 23)

    added = report.get("added_skills", [])
    if added:
        typer.echo(f"\n[+] Eklenen beceriler ({len(added)}):")
        for s in added:
            typer.echo(f"    + {s}")

    rev_exp = report.get("revised_experiences", [])
    if rev_exp:
        typer.echo(f"\n[~] Revize edilen deneyimler ({len(rev_exp)}):")
        for eid in rev_exp:
            typer.echo(f"    ~ {eid}")

    rev_proj = report.get("revised_projects", [])
    if rev_proj:
        typer.echo(f"\n[~] Revize edilen projeler ({len(rev_proj)}):")
        for pid in rev_proj:
            typer.echo(f"    ~ {pid}")

    typer.echo("-" * 47)


def show_decisions(parsed: list) -> None:
    typer.echo("\n-- LLM Secimleri " + "-" * 30)
    included = [d for d in parsed if d["include"]]
    excluded = [d for d in parsed if not d["include"]]

    typer.echo(f"\n[+] Dahil edilecek ({len(included)} kalem):")
    for d in included:
        typer.echo(f"    {d['id']:<40} {d.get('reason', '')}")

    typer.echo(f"\n[-] Cikarilacak ({len(excluded)} kalem):")
    for d in excluded:
        typer.echo(f"    {d['id']:<40} {d.get('reason', '')}")

    typer.echo("-" * 47)


@app.command()
def generate(
    job: str = typer.Option(..., help="İş ilanı dosyası (örn: jobs/google.txt)"),
    company: str = typer.Option(..., help="Şirket adı"),
    role: str = typer.Option(..., help="Pozisyon başlığı"),
    cover: bool = typer.Option(False, "--cover-letter", help="Niyet mektubu da üret"),
    lang: str = typer.Option(None, help="Dil: en | tr (config'i override eder)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="LLM kararlarını onaysız kabul et"),
):
    config = load_config()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        typer.echo("HATA: OPENROUTER_API_KEY ortam değişkeni bulunamadı.", err=True)
        raise typer.Exit(1)

    model = config["llm"]["model"]
    lang = lang or config.get("lang", "en")

    # İlan metnini oku
    job_path = Path(job)
    if not job_path.exists():
        typer.echo(f"HATA: {job} bulunamadı.", err=True)
        raise typer.Exit(1)
    job_text = job_path.read_text(encoding="utf-8")

    typer.echo(f"\n>> Pozisyon : {role} @ {company}")
    typer.echo(f"   Model    : {model}")
    typer.echo(f"   Dil      : {lang}")
    typer.echo("\n.. Havuz okunuyor...")

    pool = selector.load_pool()

    # ── ADIM 1: İlan analizi & skill gap tespiti ──
    typer.echo(".. Ilan analiz ediliyor (skill gap + aciklama revizyonu)...")
    analysis = enricher.analyze(pool, job_text, model, api_key)

    # ── ADIM 2: Kullanıcıya skill önerilerini sor ──
    suggestions = analysis.get("suggested_skills", [])
    approved_skills = prompt_skill_approval(suggestions)

    # ── ADIM 3: Onaylanan skill'leri + revizyonları uygula ──
    enriched_pool, enrich_report = enricher.apply_enrichment(
        pool, approved_skills, analysis
    )

    show_enrichment(enrich_report)

    # ── ADIM 4: LLM seçimi ──
    typer.echo(".. LLM ile kalemler seciliyor...")
    decisions, parsed = selector.run(enriched_pool, job_text, model, api_key)

    show_decisions(parsed)

    if not yes:
        override_raw = typer.prompt(
            "Override icin ID girin (virgülle ayir, bos birak = onayla)",
            default="",
        )
        if override_raw.strip():
            for item_id in [x.strip() for x in override_raw.split(",")]:
                if item_id not in decisions:
                    typer.echo(f"  ! '{item_id}' gecersiz ID, atlandi.")
                    continue
                decisions[item_id] = not decisions[item_id]
                typer.echo(f"  ~ {item_id}: {not decisions[item_id]} -> {decisions[item_id]}")

    selected = selector.filter_pool(enriched_pool, decisions)

    # ── ADIM 5: About & CV oluştur ──
    typer.echo("\n.. About paragrafi yaziliyor...")
    about = builder.generate_about(selected, job_text, role, company, lang, model, api_key)

    typer.echo(".. CV HTML olusturuluyor...")
    cv_html = builder.build_html(selected, about, config.get("template", "cv.html"))

    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_company = company.replace(" ", "_").lower()
    out_dir = Path(config.get("output_dir", "outputs")) / f"{safe_company}_{date_str}"

    typer.echo(".. PDF uretiliyor...")
    cv_path = pdf_exporter.export(cv_html, out_dir / "cv.pdf")
    typer.echo(f"\nOK  CV      -> {cv_path}")

    if cover:
        typer.echo(".. Niyet mektubu yaziliyor...")
        cl_html = cover_letter.generate(selected, job_text, role, company, lang, model, api_key)
        cl_path = pdf_exporter.export(cl_html, out_dir / "cover_letter.pdf")
        typer.echo(f"OK  Mektup -> {cl_path}")

    typer.echo(f"\nKlasor : {out_dir.resolve()}\n")


if __name__ == "__main__":
    app()
