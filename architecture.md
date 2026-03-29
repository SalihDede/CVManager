# CV Manager — Sistem Mimarisi & Süreç Adımları

## Genel Bakış

Kullanıcının tüm deneyim ve becerilerini bir **havuzda** tutar. İş ilanı verildiğinde LLM, havuzdaki her kalemi pozisyona uygunluğuna göre seçer; `about` ve niyet mektubu da LLM tarafından sıfırdan yazılır. Çıktı PDF olarak alınır.

---

## Klasör Yapısı

```
cv_manager/
├── pool/                        # Tüm ham bilgiler (tek seferlik doldurulur)
│   ├── personal.json            # Ad, iletişim, sosyal linkler (about YOK — LLM yazar)
│   ├── education.json           # Eğitim geçmişi
│   ├── experience.json          # İş / staj deneyimleri
│   ├── projects.json            # Projeler (detaylı + tags)
│   ├── skills.json              # Teknik, AI/ML, araçlar, diller
│   └── certifications.json      # Sertifikalar
│
├── templates/
│   ├── cv.html                  # Jinja2 CV şablonu (mevcut PDF tasarımına uygun)
│   └── cover_letter.html        # Niyet mektubu şablonu
│
├── outputs/
│   └── {şirket}_{tarih}/
│       ├── cv.pdf
│       └── cover_letter.pdf     # (opsiyonel)
│
├── jobs/
│   └── {şirket}_{pozisyon}.txt  # Ham ilan metni
│
├── core/
│   ├── enricher.py              # LLM → pool zenginleştirme (eksik skill + açıklama revizyonu)
│   ├── selector.py              # LLM → her kalem için include: true/false
│   ├── builder.py               # Seçilen kalemler + Jinja2 → HTML
│   ├── pdf_exporter.py          # HTML → PDF (WeasyPrint)
│   └── cover_letter.py          # LLM → niyet mektubu
│
├── main.py                      # CLI giriş noktası
├── config.yaml                  # Model, dil, şablon tercihleri
└── requirements.txt
```

---

## CV Bölümleri (Mevcut PDF'ten)

| Bölüm | Kaynak Dosya | LLM Seçimi |
|-------|-------------|------------|
| Header (isim, iletişim, linkler) | `personal.json` | Sabit — hep dahil |
| About Me | — | LLM sıfırdan yazar (pozisyona özel) |
| Experience | `experience.json` | Her kalem için ✓/✗ |
| Education | `education.json` | Her kalem için ✓/✗ |
| Skills | `skills.json` | Her skill için ✓/✗ |
| Projects | `projects.json` | Her proje için ✓/✗ |
| Certificates | `certifications.json` | Her sertifika için ✓/✗ |
| Cover Letter | — | LLM sıfırdan yazar (opsiyonel) |

---

## Süreç Adımları

### Adım 1 — Havuz (Tamamlandı ✓)

```
pool/personal.json       → 1 obje   (sabit kişisel bilgiler)
pool/experience.json     → 6 kalem  (Codeventure×2, Microsoft, Kaymakamlık, Extoget, Fiverr)
pool/education.json      → 2 kalem  (MEF Üniversitesi, Florya Final)
pool/projects.json       → 13 kalem (Kumru, Hulki, LinkedIn Bot, Personnel Tracker, ...)
pool/skills.json         → 3 grup   (technical, ai_ml, tools) + languages
pool/certifications.json → 15 kalem (Microsoft, IBM, Google, Coursera, BTK)
```

Her kalemde `tags` alanı var — LLM bu etiketlere bakarak ilan eşleşmesi yapar.

---

### Adım 2 — İlan Girişi

```bash
python main.py generate \
  --job "jobs/google_ml_engineer.txt" \
  --company "Google" \
  --role "ML Engineer" \
  --lang en              # veya tr
```

---

### Adım 3 — Pool Zenginleştirme (`enricher.py`)

İlan metni analiz edilerek havuzdaki veriler otomatik zenginleştirilir. Pool dosyaları **değişmez**, işlem bellekte yapılır.

**Ne yapar:**
1. İlandaki gereksinimleri havuzla karşılaştırır
2. Eksik skill'leri uygun seviye ve grupla ekler
3. Experience ve proje açıklamalarını ilana uygun şekilde yeniden yazar

**Prompt yapısı:**
```
TASK 1 — SKILL ENRICHMENT
İlanda istenip havuzda olmayan skill'leri bul ve ekle.
- "intermediate" → projelerden/deneyimden kanıt varsa
- "beginner"     → kanıt yoksa ama ilan istiyorsa

TASK 2 — DESCRIPTION REVISION
Mevcut deneyim ve proje açıklamalarını ilana uygun güçlendir.
- Yeni sorumluluk UYDURMA — mevcut içeriği yeniden çerçevele
- İlandaki anahtar kelimeleri doğal şekilde vurgula
```

**Çıktı:**
```
-- Zenginlestirme Raporu -----------------------
[+] Eklenen beceriler (4):
    + Neo4j (beginner, ai_ml)
    + GraphRAG (intermediate, ai_ml)
    + FastAPI (intermediate, technical)
    + Golang (beginner, technical)

[~] Revize edilen deneyimler (3):
    ~ exp_001
    ~ exp_002
    ~ exp_003

[~] Revize edilen projeler (5):
    ~ proj_003
    ~ proj_014
    ~ proj_015
    ~ proj_002
    ~ proj_001
-----------------------------------------------
```

---

### Adım 4 — LLM Seçimi (`selector.py`)

**Prompt yapısı (structured JSON output):**
```
Sen bir senior teknik recruiter ve CV uzmanısın.
Aşağıdaki iş ilanı için CV havuzundaki kalemleri değerlendir.
Her kalem için { "id": "...", "include": true/false, "reason": "..." } döndür.

Kriterler:
- İlanla teknik uyum (tags eşleşmesi)
- Pozisyon seviyesi (intern/junior/senior)
- CV uzunluğu makul kalsın (max 2 sayfa)
- Alakasız kalemler kesinlikle çıkar

İŞ İLANI:
{job_text}

HAVUZ KALEMLERİ:
{all_items_json}
```

**Çıktı örneği:**
```json
[
  { "id": "exp_001", "include": true,  "reason": "LangChain/n8n ilanla birebir örtüşüyor" },
  { "id": "exp_005", "include": false, "reason": "Embedded C bu pozisyonla alakasız" },
  { "id": "proj_001", "include": true,  "reason": "NLP fine-tuning direkt istenmiş" }
]
```

---

### Adım 5 — About Üretimi (LLM)

Seçilen kalemler belirlendikten sonra LLM, About paragrafını yazar:

```
Seçilen CV kalemleri ve iş ilanı doğrultusunda 3-4 cümlelik profesyonel bir 'About Me' yaz.
Birinci şahıs, özgüvenli ama abartısız ton.
Pozisyonla en alakalı 2-3 yetkinliği öne çıkar.

POZISYON: {role} at {company}
SEÇİLEN KALEMLERİN ÖZETİ: {selected_summary}
```

---

### Adım 6 — CV Oluşturma (`builder.py`)

```python
selected = selector.run(pool, job_text)       # LLM seçimi
about    = llm.generate_about(selected, job)  # About üretimi
html     = template.render(
    personal=personal,
    about=about,
    experience=selected.experience,
    education=selected.education,
    skills=selected.skills,
    projects=selected.projects,
    certifications=selected.certifications
)
```

---

### Adım 7 — Niyet Mektubu (Opsiyonel)

```bash
python main.py generate --job "jobs/x.txt" --cover-letter
```

```
Profesyonel niyet mektubu yaz. Dil: {lang}. Uzunluk: ~250 kelime, 3 paragraf.
Paragraf 1: Neden bu pozisyon / şirket
Paragraf 2: Seçilen 2-3 deneyim/projeyle kanıtla
Paragraf 3: Motivasyon ve katkı teklifi

POZISYON: {role} at {company}
İLAN: {job_text}
SEÇİLEN KALEMLERİN ÖZETİ: {selected_summary}
```

---

### Adım 8 — PDF Çıktısı

```python
from weasyprint import HTML
HTML(string=html).write_pdf(f"outputs/{company}_{date}/cv.pdf")
```

---

## Veri Akışı

```
[jobs/*.txt]
      │
      ▼
[pool/*.json] ──► [LLM Enricher] ──► [LLM Selector] ──► [Onay / Override (CLI)]
                        │                    │
                  [Zenginleşmiş Pool]   [Seçilen Kalemler]
                    │     │     │
                    ▼     ▼     ▼
              [About] [CV Builder] [Cover Letter]
                           │
                      [HTML Render]
                           │
                       [WeasyPrint]
                           │
                    outputs/{şirket}_{tarih}/
                       cv.pdf  +  cover_letter.pdf
```

---

## Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| Dil | Python 3.11+ |
| LLM | Claude API (`claude-sonnet-4-6`) |
| Şablon | Jinja2 + HTML/CSS |
| PDF | WeasyPrint |
| CLI | Typer |
| Veri | JSON (havuz) + YAML (config) |

---

## Geliştirme Fazları

### Faz 1 — MVP ✅ Hazır
- [x] Havuz JSON dosyaları oluşturuldu (6 dosya, gerçek CV verisi)
- [ ] `selector.py` — LLM ile kalem seçimi (structured output)
- [ ] `builder.py` — Jinja2 + mevcut CV tasarımına uygun şablon
- [ ] `pdf_exporter.py` — WeasyPrint
- [ ] `main.py` — CLI akışı

### Faz 2 — Kalite
- [ ] CLI onay ekranı (`questionary`) — override mekanizması
- [ ] About üretici
- [ ] Niyet mektubu üretici
- [ ] ATS skoru (ilan ↔ CV kelime örtüşme oranı)

### Faz 3 — Opsiyonel
- [ ] Streamlit web arayüzü
- [ ] İlan URL → otomatik scraping
- [ ] Başvuru geçmişi takibi

---

## Kritik Kararlar

1. **About LLM'e ait**: Her başvuruda sıfırdan yazılır, havuzda saklanmaz.
2. **Structured output zorunlu**: JSON mode kullan — parse hatalarını önler.
3. **Tags kritik**: Her havuz kalemi `tags` içermeli; LLM eşleşme için bunu kullanır.
4. **Override zorunlu**: LLM kararı öneri, kullanıcı kararı son söz.
5. **ATS uyumu**: Şablonda tablo/grafik/progress bar kullanma — sade HTML.
