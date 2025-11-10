# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projektübersicht

**Traffective AI Tools** ist eine Streamlit-basierte Webanwendung zur automatisierten SEO-Artikel-Generierung im Bereich Programmatic Advertising und Entertainment-Content (Promipool).

Die Anwendung unterstützt:
- Multi-Source Content Aggregation (URLs, PDF, Textinput)
- KI-gestützte Artikel-Generierung mit OpenAI und Anthropic
- SEO-Optimierung mit automatischer Kategorisierung
- API-Integration für Content-Management-Systeme
- Quellenbasierte Zitierung und Faktenextraktion

## Entwicklungsumgebung

### Installation und Setup
```bash
# Installation mit uv (empfohlen)
uv pip install -e .

# Oder mit pip
pip install -e .

# Development Dependencies
pip install -e ".[dev]"
```

### Application starten
```bash
streamlit run promipool.py
```

Die Hauptanwendung ist unter `promipool.py` verfügbar. Zusätzliche Tools befinden sich im `pages/` Verzeichnis und werden automatisch von Streamlit als Multi-Page-App erkannt.

### Code Quality Tools
```bash
# Code formatieren
black .

# Linting
ruff check .

# Tests ausführen (falls vorhanden)
pytest
```

## Architektur

### Hauptkomponenten

**1. Multi-Source Content Processing**
- `process_multiple_urls()`: Scraping mit newspaper3k + Jina.ai Fallback
- `process_pdf()`: PDF-Text-Extraktion mit PyPDF2
- URL-basierter Content wird mit `Article` von newspaper3k extrahiert

**2. SEO Article Generation Pipeline**
Die Kern-Logik befindet sich in `process_text_for_seo_enhanced_promipool()`:
- **Automatische Kategorisierung**: `analyze_theme_module_promipool_original()` erkennt Promipool-Kategorien (ROYALS, STARS, TV_FILM, RETRO, SCHLAGER, STYLE)
- **Quellenverarbeitung**: `create_source_info_promipool()` erstellt strukturierte Quellenangaben mit Entertainment-Domain-Mapping
- **Zitat-Extraktion**: `extract_real_quotes_from_source_promipool()` extrahiert direkte Zitate aus Quelltext
- **Fakten-Extraktion**: `extract_concrete_facts_promipool()` findet Entertainment-Fakten (Follower, Quoten, Alter, etc.)

**3. Prompt Engineering**
Der Hauptprompt in `process_text_for_seo_enhanced_promipool()` enthält:
- Anti-Halluzinations-Regeln für journalistische Genauigkeit
- Promipool-spezifische Stilrichtlinien (emotional aber seriös)
- Quellen-Zitierungsregeln (kursive Formatierung: *Quelle*)
- Anti-KI-Stil-Filter (verhindert typische KI-Phrasen)

**4. Article Components Extraction**
`extract_article_components()` parst den generierten Artikel in:
- Titel (max. 60 Zeichen, dramatisch)
- Untertitel (max. 20 Zeichen, 3-4 Wörter)
- Abstract (teaser ohne Spoiler)
- Artikeltext (mit ### Zwischenüberschriften)
- Metabeschreibung (150-160 Zeichen, SEO-optimiert)

**5. CMS Integration**
- `send_article_to_pp()`: POST zu Promipool API mit Header-Konvertierung (### → #)
- `format_content_for_api()`: Konvertiert Display-Format zu CMS-kompatiblem Format

**6. Streamlit Fragments**
- `@st.experimental_fragment` für partielle Updates ohne Full-Page-Reload
- `display_article()`: Zeigt generierten Artikel
- `edit_article()`: Erlaubt Nachbearbeitung mit zusätzlichen Infos
- `send_article_to_pp_fragment()`: API-Versand

### Wichtige Module

**Material Verzeichnis**
- `material/07-BPM_Multisource_Claude_V4.py`: Business Punk Version (ähnlicher Workflow, andere Domänen und Stil)
- Enthält Business-fokussierte Quellenverarbeitung und andere Kategorisierung

**Pages Verzeichnis**
- `pages/07-PP_Article_07_25_v3.py`: Ältere Version oder alternative Implementierung
- Streamlit Multi-Page-App Struktur

## Wichtige Implementierungsdetails

### Quellenangaben-System
- Alle Quellennamen werden **kursiv** formatiert: `*Bild.de*`, `*RTL.de*`
- Variation der Formulierungen ist Pflicht: "laut *Quelle*", "*Quelle* berichtet", "wie *Quelle* meldet"
- Pro Absatz maximal 1-2 strategische Quellenangaben (Balance zwischen Credibility und Lesbarkeit)

### Zitat-Handling
- Nur **direkte Zitate** aus Originalquellen werden verwendet
- Zitate müssen ins Deutsche übersetzt werden
- Format: „Zitat", so *Quellenname*
- Bei mehreren Quellen: "so berichten mehrere Medien"

### Anti-KI-Stil-Filter
Das System filtert aktiv KI-typische Phrasen:
- Vermeidet: "[Name], bekannt aus [Show], hat..."
- Bevorzugt: "[Beruf] [Name]" oder direkt "[Name]"
- Verhindert übermäßige Verwendung von Konjunktionen ("könnte", "möglicherweise")

### Markdown-Formatierung
- Display-Format: `###` für Zwischenüberschriften
- API-Format: `#` für CMS-Kompatibilität
- Konvertierung erfolgt in `format_content_for_api()`

## Secrets Management

Die Anwendung benötigt Streamlit Secrets (`.streamlit/secrets.toml`):
- `openai`: OpenAI API Key
- Google Sheets Credentials (alle `gs-*` Felder)
- `wp_bpm`: WordPress Authorization Key (für Business Punk)

**Wichtig**: API-Keys sind teilweise hardcoded im Code (z.B. in `pages/07-PP_Article_07_25_v3.py` Zeilen 23-26). Diese sollten in Secrets ausgelagert werden.

## Bekannte Einschränkungen

1. **Hardcoded API Keys**: Promipool API Keys sind im Code sichtbar (Sicherheitsrisiko)
2. **Google Sheets Integration**: Teilweise auskommentiert, scheint nicht aktiv genutzt
3. **Telegram Notification**: Bot Token ist hardcoded in `send_telegram_notification()`
4. **Error Handling**: Minimales Error Handling bei API-Calls

## Code-Stil

- **Line Length**: 100 Zeichen (Black & Ruff konfiguriert)
- **Python Version**: >=3.10
- **Type Hints**: Partiell verwendet (z.B. `-> str`, `-> dict`)
- **Docstrings**: Vorhanden bei wichtigen Funktionen, aber nicht konsistent

## Promipool-spezifische Besonderheiten

### Kategorien (Module)
- ROYALS: Königshäuser und Adel
- STARS: Allgemeine Prominenten-News
- TV_FILM: TV, Film und Streaming
- RETRO: Kult-Stars und Nostalgie
- SCHLAGER: Schlager-Musik
- STYLE: Fashion und Beauty

Kategorisierung erfolgt über Keyword-Matching mit gewichteten Priority-Keywords.

### Tonalität
- Emotional aber respektvoll ("zerrüttet" statt "angespannt")
- Moderate Spannung ("Das wird spannend!", "Endlich Bewegung")
- Max. 2-3 Ausrufezeichen pro Artikel
- Seriös bleiben - keine Reißersprache

### Titel-Requirements
- Max. 60 Zeichen
- Dramatisch und emotional
- Promipool-Drama-Vokabular: "Sensation", "Geheim", "Wendepunkt"
- Konsistente Dramatik zwischen Titel und Untertitel
