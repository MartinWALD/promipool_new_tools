from openai import OpenAI
import time
from rich import print
import requests
import pandas as pd
import streamlit as st
from newspaper import Article
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import re
import PyPDF2
import io

# Page configuration
st.set_page_config(
    page_title="BizDaily Article Generator",
    page_icon="💼",
    layout="wide"
)

# Define the API key and server URL
API_KEY = "TfrBdFP-dEYYXdL4stRuG8frztLhRf_sEMfuZkPrhi2-Fpq2R"
SERVER_URL = "https://p1.promipool.de/api/articles"
PP_API_KEY = "7cd84bed39a44cdd53c256431aa47c55f284985b"
PP_SERVER_URL ="https://www.promipool.de/api/content-drafts/create"

# Setup the gspread authentication using the details from Streamlit secrets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_dict({
    "type": "service_account",
    "project_id": st.secrets["gs-project_id"],
    "private_key_id": st.secrets["gs-private_key_id"],
    "private_key": st.secrets["gs-private_key"],
    "client_email": st.secrets["gs-client_email"],
    "client_id": st.secrets["gs-client_id"],
    "auth_uri": st.secrets["gs-auth_uri"],
    "token_uri": st.secrets["gs-token_uri"],
    "auth_provider_x509_cert_url": st.secrets["gs-auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["gs-client_x509_cert_url"]
}, scope)

client_gspread = gspread.authorize(credentials)

# Initialize the Google Sheet and worksheet (optional - app continues without it)
try:
    spreadsheet = client_gspread.open("Lifestyle_Verbraucher_AI_Logs")
    worksheet = spreadsheet.worksheet("Articles")
    st.info("✅ Google Sheets Logging aktiv")
except Exception as e:
    worksheet = None
    st.warning(f"⚠️ Google Sheets Logging nicht verfügbar: {str(e)}\n\nDie App funktioniert trotzdem normal, Artikel-Logs werden nicht gespeichert.")

# Streamlit UI layout
col1, col2, col3 = st.columns(3)

def create_source_info_lifestyle(urls, uploaded_file=None, user_text_provided=False, url_contents=None):
    """
    Erstellt erweiterte Quelleninfo für bessere Zitierung im Lifestyle/Verbraucher Artikel.
    """
    from urllib.parse import urlparse

    def extract_domain_info(url):
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')

            # Lifestyle/Verbraucher-Quellen-Mapping
            lifestyle_source_mapping = {
                # Verbraucher & Finanzen
                'finanztip.de': ('Finanztip', 'Verbraucher-Portal Finanztip', 'Finanz- und Verbrauchertipps'),
                'test.de': ('Stiftung Warentest', 'Verbraucherorganisation Stiftung Warentest', 'Produkt-Tests und Verbraucherschutz'),
                'verbraucherzentrale.de': ('Verbraucherzentrale', 'Verbraucherzentrale', 'Verbraucherschutz und Beratung'),

                # Renten & Soziales
                'deutsche-rentenversicherung.de': ('Deutsche Rentenversicherung', 'Deutsche Rentenversicherung', 'Renten-Informationen'),
                'sozialverband.de': ('Sozialverband', 'Sozialverband', 'Sozial- und Rentenrecht'),

                # News & Wirtschaft
                'spiegel.de': ('Spiegel', 'Nachrichtenmagazin Spiegel', 'Wirtschafts- und Verbrauchernews'),
                'focus.de': ('Focus', 'Nachrichtenmagazin Focus', 'Verbraucher- und Finanznews'),
                'stern.de': ('Stern', 'Nachrichtenmagazin Stern', 'Lifestyle und Verbraucherthemen'),
                'welt.de': ('Welt', 'Tageszeitung Die Welt', 'Wirtschafts- und Verbrauchernews'),
                't-online.de': ('t-online.de', 'Online-Portal t-online.de', 'Verbrauchernews'),
                'bild.de': ('Bild', 'Boulevard-Zeitung Bild', 'Verbraucher- und Lifestyle-News'),
                'zeit.de': ('Zeit', 'Wochenzeitung Die Zeit', 'Wirtschafts- und Gesellschaftsnews'),
                'handelsblatt.com': ('Handelsblatt', 'Wirtschaftszeitung Handelsblatt', 'Wirtschaftsnachrichten'),
                'ifo.de': ('ifo Institut', 'ifo Institut München', 'Wirtschaftsforschung'),

                # Finanz & Versicherung
                'check24.de': ('Check24', 'Vergleichsportal Check24', 'Finanz- und Versicherungsvergleiche'),
                'verivox.de': ('Verivox', 'Vergleichsportal Verivox', 'Tarif-Vergleiche'),
                'finanzen.net': ('Finanzen.net', 'Finanzportal Finanzen.net', 'Börsen- und Finanznews'),

                # Lifestyle & Wohnen
                'schoener-wohnen.de': ('Schöner Wohnen', 'Lifestyle-Magazin Schöner Wohnen', 'Wohn- und Einrichtungstrends'),
                'brigitte.de': ('Brigitte', 'Frauenmagazin Brigitte', 'Lifestyle und Verbraucherthemen'),
            }

            for key, (name, description, content_focus) in lifestyle_source_mapping.items():
                if key in domain.lower():
                    return domain, name, description, content_focus

            return domain, domain, f"Online-Quelle {domain}", "Verbraucher-Informationen"

        except Exception:
            return url, url, f"Online-Quelle {url}", "allgemeine Informationen"

    if not url_contents:
        url_contents = {}

    source_info = "QUELLENVERZEICHNIS FÜR LIFESTYLE/VERBRAUCHER ARTIKEL:\n"
    source_names = []

    for i, url in enumerate(urls, 1):
        if url.strip():
            domain, source_name, source_description, content_focus = extract_domain_info(url)
            source_info += f"Quelle {i}: {source_description} ({domain})\n"
            source_names.append(source_name)

    if uploaded_file is not None:
        source_info += f"Quelle {len(urls) + 1}: Hochgeladenes Dokument\n"
        source_names.append("Hochgeladenes Dokument")

    if user_text_provided:
        source_info += f"Quelle {len(urls) + (1 if uploaded_file else 0) + 1}: Nutzereingabe\n"
        source_names.append("Nutzereingabe")

    if source_names:
        formatted_sources = ', '.join([f'"{name}"' for name in source_names])
        source_info += f"\n\nQUELLEN FÜR ARTIKEL:\n{formatted_sources}"

    return source_info

def analyze_theme_module_lifestyle(article_text: str, source_info: str = "") -> str:
    """
    Erkennt die Lifestyle/Verbraucher-Kategorie automatisch
    """
    full_text = (article_text + " " + source_info).lower()

    modules = {
        'WIRTSCHAFT': {
            'keywords': ['wirtschaft', 'industrie', 'unternehmen', 'wettbewerb', 'wettbewerbsfähigkeit', 'export', 'konjunktur', 'ifo', 'geschäftsklima', 'standort', 'produktion', 'maschinenbau', 'chemische industrie', 'energiepreis', 'handel', 'börse', 'dax'],
            'high_priority': ['wirtschaft', 'industrie', 'unternehmen', 'wettbewerbsfähigkeit', 'ifo institut', 'konjunktur', 'export']
        },
        'RENTE': {
            'keywords': ['rente', 'rentenversicherung', 'altersvorsorge', 'rentner', 'pensionär', 'ruhestand', 'rentenanspruch', 'rentenerhöhung', 'grundrente', 'erwerbsminderungsrente'],
            'high_priority': ['rente', 'rentenversicherung', 'altersvorsorge', 'rentner', 'grundrente']
        },
        'FINANZEN': {
            'keywords': ['geld', 'finanzen', 'sparen', 'kredit', 'investieren', 'zinsen', 'bank', 'versicherung', 'steuern', 'vermögen'],
            'high_priority': ['finanzen', 'geld', 'sparen', 'kredit', 'investieren']
        },
        'VERBRAUCHER': {
            'keywords': ['verbraucher', 'verbraucherschutz', 'test', 'produkt', 'qualität', 'preisvergleich', 'reklamation', 'garantie', 'kundenrecht'],
            'high_priority': ['verbraucher', 'verbraucherschutz', 'test', 'produkt']
        },
        'GESUNDHEIT': {
            'keywords': ['gesundheit', 'krankenkasse', 'arzt', 'medizin', 'pflege', 'krankenversicherung', 'therapie', 'vorsorge'],
            'high_priority': ['gesundheit', 'krankenkasse', 'pflege', 'krankenversicherung']
        },
        'WOHNEN': {
            'keywords': ['wohnen', 'miete', 'immobilie', 'eigentum', 'wohnung', 'haus', 'nebenkosten', 'mietrecht', 'eigentümer'],
            'high_priority': ['wohnen', 'miete', 'immobilie', 'wohnung']
        },
        'LIFESTYLE': {
            'keywords': ['lifestyle', 'mode', 'reisen', 'urlaub', 'freizeit', 'hobby', 'ernährung', 'fitness', 'wellness'],
            'high_priority': ['lifestyle', 'reisen', 'urlaub', 'ernährung']
        }
    }

    scores = {}
    for module_name, module_data in modules.items():
        score = 0
        for keyword in module_data['keywords']:
            score += full_text.count(keyword)
        for priority_keyword in module_data['high_priority']:
            score += full_text.count(priority_keyword) * 5
        scores[module_name] = score

    if max(scores.values()) == 0:
        return 'VERBRAUCHER'

    primary_module = max(scores, key=scores.get)

    return primary_module

def get_module_info_lifestyle(module_key: str) -> dict:
    """
    Gibt Informationen zur erkannten Kategorie zurück
    """
    modules_info = {
        'WIRTSCHAFT': {
            'name': 'Wirtschaft & Industrie',
            'focus': 'Wirtschafts-News, Industrie und Unternehmen',
            'hashtags': ['#Wirtschaft', '#Industrie', '#Unternehmen', '#Standort', '#Konjunktur']
        },
        'RENTE': {
            'name': 'Rente & Altersvorsorge',
            'focus': 'Renten-News, Altersvorsorge und Ruhestand',
            'hashtags': ['#Rente', '#Altersvorsorge', '#Ruhestand', '#Rentner', '#Finanzen']
        },
        'FINANZEN': {
            'name': 'Finanzen & Geld',
            'focus': 'Finanz-Tipps, Sparen und Vermögen',
            'hashtags': ['#Finanzen', '#Geld', '#Sparen', '#Investieren', '#Vermögen']
        },
        'VERBRAUCHER': {
            'name': 'Verbraucher & Tests',
            'focus': 'Verbraucherschutz und Produkt-Tests',
            'hashtags': ['#Verbraucher', '#Test', '#Qualität', '#Produkt', '#Verbraucherschutz']
        },
        'GESUNDHEIT': {
            'name': 'Gesundheit & Pflege',
            'focus': 'Gesundheits-Themen und Krankenversicherung',
            'hashtags': ['#Gesundheit', '#Krankenkasse', '#Pflege', '#Medizin', '#Vorsorge']
        },
        'WOHNEN': {
            'name': 'Wohnen & Immobilien',
            'focus': 'Miete, Immobilien und Wohnrecht',
            'hashtags': ['#Wohnen', '#Miete', '#Immobilien', '#Mietrecht', '#Nebenkosten']
        },
        'LIFESTYLE': {
            'name': 'Lifestyle & Freizeit',
            'focus': 'Lifestyle-Themen und Freizeitgestaltung',
            'hashtags': ['#Lifestyle', '#Reisen', '#Urlaub', '#Freizeit', '#Wellness']
        }
    }

    return modules_info.get(module_key, modules_info['VERBRAUCHER'])

def extract_real_quotes_from_source_lifestyle(text):
    """
    Extrahiert direkte Zitate aus dem Quellentext
    """
    import re
    quotes = []

    patterns = [
        r'"([^"]{15,250})"',
        r'„([^"]{15,250})"',
        r"'([^']{15,250})'"
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if not any(x in match for x in [
                '|', ':', 'Breaking', 'News', 'Copyright', 'Anzeige', 'Image',
                'Learn More', 'Akzeptieren', 'Cookie', 'Datenschutz', 'Impressum',
                'Menü', 'Ressorts', 'Untermenü', 'Newsletter', 'Abo', 'Login'
            ]):
                if any(term in match.lower() for term in [
                    'ich', 'mein', 'mir', 'bin', 'habe', 'will', 'kann', 'möchte',
                    'wir', 'uns', 'unser', 'unsere', 'werden', 'sind'
                ]):
                    if len(match) > 20:
                        quotes.append(match.strip())

    unique_quotes = []
    for quote in sorted(quotes, key=len, reverse=True):
        is_duplicate = False
        for existing in unique_quotes:
            if quote.lower() in existing.lower() or existing.lower() in quote.lower():
                is_duplicate = True
                break
        if not is_duplicate:
            unique_quotes.append(quote)

    return unique_quotes[:5]

def extract_sources_from_info_lifestyle(source_info):
    """
    Extrahiert Quellennamen für Zitierung
    """
    import re
    sources = []

    pattern = r'Quelle\s+\d+:\s+([^(]+)\s*\(([^)]+)\)'
    matches = re.findall(pattern, source_info)

    for description, domain in matches:
        if 'finanztip' in description.lower():
            sources.append('Finanztip')
        elif 'stiftung warentest' in description.lower():
            sources.append('Stiftung Warentest')
        elif 'verbraucherzentrale' in description.lower():
            sources.append('Verbraucherzentrale')
        elif 'spiegel' in description.lower():
            sources.append('Spiegel')
        elif 'focus' in description.lower():
            sources.append('Focus')
        elif 'bild' in description.lower():
            sources.append('Bild')
        elif 'handelsblatt' in description.lower():
            sources.append('Handelsblatt')
        elif 'welt' in description.lower():
            sources.append('Welt')
        elif 't-online' in description.lower():
            sources.append('t-online.de')
        elif 'ifo' in description.lower() or 'institut' in domain.lower():
            sources.append('ifo Institut')
        elif 'zeit' in description.lower():
            sources.append('Zeit')
        else:
            clean_domain = domain.replace('www.', '').replace('.de', '').replace('.com', '')
            sources.append(clean_domain.capitalize())

    return sources

def extract_concrete_facts_lifestyle(text):
    """
    Extrahiert konkrete Fakten und Zahlen aus dem Quellentext
    """
    import re
    facts = []

    patterns = [
        # Zahlen und Beträge
        r'\d+(?:\.\d+)?\s*(?:Euro|€|Dollar|\$|Prozent|%)',
        r'\d+(?:,\d+)?\s*(?:Euro|€|Prozent|%)',

        # Zeitangaben
        r'(?:seit|ab|vor|in)\s+\d{4}',
        r'\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}',

        # Statistische Angaben
        r'\d+(?:\.\d+)?\s*(?:Millionen|Mio\.|Milliarden|Mrd\.)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) > 3:
                facts.append(match.strip())

    facts = list(set(facts))
    facts.sort(key=len, reverse=True)

    return facts[:10]

def convert_source_quotes_to_german(text):
    """Konvertiert englische Anführungszeichen bei Quellenangaben zu deutschen"""
    import re

    source_patterns = [
        (r'laut "([^"]+)"', r'laut „\1"'),
        (r'so "([^"]+)" berichtet', r'so „\1" berichtet'),
        (r'wie "([^"]+)" meldet', r'wie „\1" meldet'),
        (r'heißt es bei "([^"]+)"', r'heißt es bei „\1"'),
        (r'"([^"]+)" enthüllt', r'„\1" enthüllt'),
        (r'"([^"]+)" berichtet', r'„\1" berichtet'),
    ]

    for pattern, replacement in source_patterns:
        text = re.sub(pattern, replacement, text)

    return text

def truncate_text_for_sheets(text: str, max_length: int = 45000) -> str:
    """
    Truncates text to ensure it fits within Google Sheets cell limits.
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    truncated_text = text[:max_length]
    truncation_indicator = "... [TEXT TRUNCATED DUE TO LENGTH]"

    final_text = truncated_text[:max_length - len(truncation_indicator)] + truncation_indicator
    return final_text

def update_google_sheet(date: str, time: str, source: str, original_text: str,
                    result_text: str, video_article_long: str = "", video_article_short: str = "", tool: str = "") -> tuple[bool, str]:
    """
    Updates Google Sheet with article generation data (Standard + Video-Artikel Lang + Kurz).
    Scripts wurden entfernt - nur noch die 3 Hauptformate werden gespeichert.
    """
    # Check if worksheet is available
    if worksheet is None:
        return True, "Google Sheets logging is disabled (spreadsheet not available)"

    try:
        truncated_source = truncate_text_for_sheets(source)
        truncated_original = truncate_text_for_sheets(original_text)
        truncated_result = truncate_text_for_sheets(result_text)
        truncated_video_article_long = truncate_text_for_sheets(video_article_long)
        truncated_video_article_short = truncate_text_for_sheets(video_article_short)

        worksheet.append_row([
            date,
            time,
            truncated_source,
            truncated_original,
            truncated_result,
            truncated_video_article_long,
            truncated_video_article_short,
            tool
        ])

        was_truncated = (len(source) > 45000 or
                        len(original_text) > 45000 or
                        len(result_text) > 45000 or
                        len(video_article_long) > 45000 or
                        len(video_article_short) > 45000)

        if was_truncated:
            return True, "Data saved successfully but some fields were truncated due to length limits"
        return True, "Data saved successfully"

    except Exception as e:
        error_message = f"Failed to save to Google Sheets: {str(e)}"
        return False, error_message

def process_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# OpenAI Client mit GPT-4o (schnell und zuverlässig)
def generate_text(prompt, model="gpt-4o-2024-08-06", temperature=0.5, max_retries=3):
    client = OpenAI(api_key=st.secrets["openai"], max_retries=max_retries, timeout=180.0)
    messages = [{"role": "user", "content": prompt}]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        result = response.choices[0].message.content.strip()
        return result

    except Exception as e:
        error_msg = f"❌ OpenAI API Fehler mit {model}: {str(e)}"
        st.error(error_msg)
        raise Exception(error_msg)

def remove_markdown(text):
    """
    Erweiterte Funktion zum Entfernen von Markdown-Formatierung.
    """
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1', text)
    text = re.sub(r'^\#{1,6}\s*(.+)', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,2}([^\*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'\_{1,2}([^\_]+)\_{1,2}', r'\1', text)
    text = text.replace('`', '')
    text = text.replace('> ', '')
    return text

@st.experimental_fragment
def send_article_to_pp_fragment():
    if 'title' not in st.session_state or 'subtitle' not in st.session_state or 'content' not in st.session_state or 'meta' not in st.session_state:
        st.warning("Please generate an article first before sending to API.")
        return

    if st.button("Send Article to API"):
        with st.spinner("📤 Sende Artikel an Promipool API..."):
            title = st.session_state.get('title', '').strip()
            subtitle = st.session_state.get('subtitle', '').strip()
            abstract = st.session_state.get('abstract', '').strip()
            content = st.session_state.get('content', '').strip()
            meta = st.session_state.get('meta', '').strip()

            if not title or not subtitle:
                st.error("❌ Titel und Untertitel sind erforderlich.")
                return

            api_response = send_article_to_pp(title, subtitle, abstract, content, meta)

            # Check erfolgreicher Response
            if api_response.get('success'):
                st.success("✅ Der Artikel wurde erfolgreich an Promipool API gesendet!")
            else:
                st.error(f"❌ Fehler beim Senden des Artikels: {api_response.get('error', 'Unbekannter Fehler')}")
                with st.expander("🔍 Fehler-Details anzeigen"):
                    st.json(api_response)

def send_article_to_pp(title: str, subtitle: str, abstract: str, content: str, meta: str = None) -> dict:
    """
    Send article to API with header conversion.
    """
    headers = {
        'x-authentification-token': PP_API_KEY
    }

    formatted_content = format_content_for_api(content)

    files = {
        'title': (None, title),
        'subtitle': (None, subtitle),
        'content': (None, formatted_content),
        'meta': (None, meta if meta else "")
    }

    if abstract:
        files['abstract'] = (None, abstract)

    try:
        response = requests.post(
            PP_SERVER_URL,
            headers=headers,
            files=files,
            timeout=30
        )

        if response.status_code in (200, 201):
            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.json() if response.text else {},
                "message": "Artikel erfolgreich gesendet"
            }
        else:
            return {
                "success": False,
                "error": f"HTTP Status Code: {response.status_code}",
                "status_code": response.status_code,
                "response_text": response.text[:500],  # Erste 500 Zeichen der Antwort
                "url": PP_SERVER_URL
            }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request Timeout - API antwortet nicht innerhalb von 30 Sekunden",
            "url": PP_SERVER_URL
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "error": f"Verbindungsfehler zur API: {str(e)}",
            "url": PP_SERVER_URL
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unbekannter Fehler: {str(e)}",
            "error_type": type(e).__name__,
            "url": PP_SERVER_URL
        }

def clean_article_text(text: str, is_intro: bool = False) -> str:
    """
    Clean article text while preserving markdown structure.
    """
    if not text:
        return ""

    if is_intro:
        text = text.strip('"')

    paragraphs = text.split('\n\n')
    cleaned_paragraphs = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            continue

        lines = paragraph.strip().split('\n')
        cleaned_lines = []

        for line in lines:
            clean_line = line.strip()

            if not clean_line:
                continue

            if clean_line.startswith('##'):
                clean_line = clean_line.replace('##', '').strip()
                cleaned_lines.append(clean_line)
                continue

            if clean_line.startswith('**') and clean_line.endswith('**'):
                clean_line = clean_line[2:-2].strip()

            clean_line = clean_line.replace('*', '')

            if clean_line.startswith('Artikeltext:'):
                continue

            cleaned_lines.append(clean_line)

        if cleaned_lines:
            cleaned_paragraphs.append('\n'.join(cleaned_lines))

    return '\n\n'.join(cleaned_paragraphs)

def extract_article_components(article_result: str) -> tuple:
    """
    Extract components from GPT's output, cleaning up formatting.
    """
    title_pattern = r"Titel:\s*(.*?)(?:\n|$)"
    subtitle_pattern = r"Untertitel:\s*(.*?)(?:\n|$)"
    abstract_pattern = r"Abstract:\s*(.*?)(?:\n{2,}|Artikeltext:)"
    meta_pattern = r"Metabeschreibung:\s*(.*?)(?:\nKeywords:|$)"

    title = re.search(title_pattern, article_result, re.DOTALL)
    subtitle = re.search(subtitle_pattern, article_result, re.DOTALL)
    abstract = re.search(abstract_pattern, article_result, re.DOTALL)
    meta = re.search(meta_pattern, article_result, re.DOTALL)

    # Extract content
    content = article_result
    if title:
        content = re.sub(title_pattern, "", content, flags=re.DOTALL).strip()
    if subtitle:
        content = re.sub(subtitle_pattern, "", content, flags=re.DOTALL).strip()
    if abstract:
        content = re.sub(abstract_pattern, "", content, flags=re.DOTALL).strip()
    if meta:
        content = re.sub(r"Metabeschreibung:.*?(?:\nKeywords:.*?)?$", "", content, flags=re.DOTALL).strip()

    # Clean extracted fields
    def clean_field(text):
        if not text:
            return ""
        # Remove leading/trailing **
        text = re.sub(r'^\*{2,}\s*', '', text)
        text = re.sub(r'\s*\*{2,}$', '', text)
        # Remove newlines and extra spaces
        text = text.replace('\n', ' ').strip()
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        return text

    clean_title = clean_field(title.group(1) if title else "")
    clean_subtitle = clean_field(subtitle.group(1) if subtitle else "")
    clean_abstract = clean_field(abstract.group(1) if abstract else "")
    clean_meta = clean_field(meta.group(1) if meta else "")

    # FALLBACK: Wenn Titel leer ist, versuche ihn aus dem Abstract/Content zu generieren
    if not clean_title or len(clean_title.strip()) == 0:
        # Versuche ersten Satz aus Abstract als Titel zu nehmen (max 60 Zeichen)
        if clean_abstract:
            fallback_title = clean_abstract.split('.')[0].strip()
            clean_title = fallback_title[:60] if len(fallback_title) > 60 else fallback_title
        else:
            clean_title = "Artikel ohne Titel - Bitte manuell ergänzen"

    # FALLBACK: Wenn Untertitel leer ist, setze Standardtext
    if not clean_subtitle or len(clean_subtitle.strip()) == 0:
        clean_subtitle = "Weitere Informationen"

    # Clean content - remove "Artikeltext:" labels and **
    clean_content = re.sub(r"Artikeltext:\s*\n*", "", content, flags=re.MULTILINE)
    clean_content = re.sub(r'^\*{2,}\s*', '', clean_content, flags=re.MULTILINE)
    clean_content = clean_content.strip()

    return (
        clean_title,
        clean_subtitle,
        clean_abstract,
        clean_content,
        clean_meta
    )


def format_content_for_api(content: str) -> str:
    """
    Format content for API by converting ### headers to # for CMS compatibility.
    """
    lines = content.split('\n')
    formatted_lines = []

    for line in lines:
        if line.strip().startswith('###'):
            formatted_lines.append(line.replace('###', '#', 1))
        else:
            formatted_lines.append(line)

    return '\n'.join(formatted_lines)

@st.experimental_fragment
def display_article():
    """Zeigt nur den Artikel an"""
    article_display = st.empty()

    _ = st.session_state.get('update_counter', 0)

    if 'content' in st.session_state:
        article_display.markdown(f"""# Generated Article Content:

Titel: {st.session_state.title}

Untertitel: {st.session_state.subtitle}

Abstract: {st.session_state.abstract}

Artikeltext:
{st.session_state.content}

Metabeschreibung: {st.session_state.meta}
""")
        return article_display


@st.experimental_fragment
def edit_article(article_display):
    """Enthält nur die Bearbeitungsfunktionen"""
    if 'content' not in st.session_state:
        return

    with st.expander("Artikel überarbeiten", expanded=False):
        additional_info = st.text_area(
            "Zusätzliche Informationen für die Überarbeitung:",
            help="Geben Sie hier weitere Informationen ein, die in den Artikel integriert werden sollen.",
            key="additional_info",
            height=150
        )

        if st.button("Artikel überarbeiten", key="enhance_button"):
            with st.spinner('Artikel wird überarbeitet...'):
                original_article = f"""Titel:
{st.session_state.title}

Untertitel:
{st.session_state.subtitle}

Abstract:
{st.session_state.abstract}

Artikeltext:
{st.session_state.content}

Metabeschreibung:
{st.session_state.meta}
"""

                enhancement_prompt = f"""Überarbeite den folgenden Artikel unter Berücksichtigung der zusätzlichen Informationen.
                Der überarbeitete Artikel soll:
                - Die zusätzlichen Informationen nahtlos in den bestehenden Text integrieren
                - Die ursprüngliche Struktur und SEO-Optimierung beibehalten
                - Alle bestehenden Formatierungen (###, Absätze etc.) beibehalten
                - Die originalen Zitate unverändert lassen
                - Die gleiche Struktur wie der Originalartikel behalten:
                    * Titel
                    * Untertitel
                    * Abstract
                    * Artikeltext (mit ### Überschriften)
                    * Metabeschreibung

                Originalartikel:
                {original_article}

                Zusätzliche Informationen zur Integration:
                {additional_info}
                """

                enhanced_article = generate_text(enhancement_prompt)

                title, subtitle, abstract, content, meta = extract_article_components(enhanced_article)

                st.session_state.title = title
                st.session_state.subtitle = subtitle
                st.session_state.abstract = abstract
                st.session_state.content = content
                st.session_state.meta = meta

                article_display.markdown(f"""# Generated Article Content:

Titel: {st.session_state.title}

Untertitel: {st.session_state.subtitle}

Abstract: {st.session_state.abstract}

Artikeltext:
{st.session_state.content}

Metabeschreibung: {st.session_state.meta}
""")

                st.success("Artikel wurde erfolgreich überarbeitet!")

def process_text_for_seo_enhanced_lifestyle(article_text: str, source_info: str = "", custom_instructions: str = "") -> str:
    """
    SEO-Funktion für Lifestyle/Verbraucher-Artikel mit angepasster Tonalität
    """
    primary_module = analyze_theme_module_lifestyle(article_text, source_info)
    module_info = get_module_info_lifestyle(primary_module)

    print(f"🎯 Erkannte Kategorie: {module_info['name']} ({primary_module})")
    print(f"📊 Fokus: {module_info['focus']}")

    real_quotes = extract_real_quotes_from_source_lifestyle(article_text)
    concrete_facts = extract_concrete_facts_lifestyle(article_text)
    available_sources = extract_sources_from_info_lifestyle(source_info)

    base_prompt = f"""KRITISCHE ANTI-HALLUZINATIONS-REGELN FÜR LIFESTYLE/VERBRAUCHER-ARTIKEL:

1. QUELLEN UND ZITATE (Verbraucher/Wirtschafts-fokussiert):
    - Verfügbare Quellen: {', '.join(available_sources) if available_sources else 'Nutze die Quellen aus der Quellenliste'}

   WICHTIG FÜR BIZ-DAILY-QUELLENANGABEN:
    - ALLE Quellennamen im Text IMMER kursiv: *Finanztip*, *Handelsblatt*, *ifo Institut*, *Stiftung Warentest*, *Bild*, *Zeit*
    - IMMER kursiv hervorgehoben: laut *Handelsblatt*
    - FORMAT: laut *Quelle*, *Quelle* berichtet, wie *Quelle* meldet, so *Quelle*
    - BEISPIELE: laut *ifo Institut*, so *Handelsblatt* berichtet, wie *Finanztip* meldet

   ZITATE (Experten-Fokus):
    - ABSOLUT KRITISCH: JEDES Zitat SOFORT mit Quelle
    - Format: „Zitat hier", so *Quellenname*
    - WORTGETREUE ÜBERNAHME: Zitate müssen EXAKT übernommen werden
    - DEUTSCHE ÜBERSETZUNG: Alle Zitate müssen ins Deutsche übersetzt werden

   FAKTEN-QUELLENANGABEN (1x pro Absatz):
    - EXTREM WICHTIG: Mindestens eine strategische Quellenangabe pro Absatz
    - WANN: Bei wichtigen Zahlen, Daten, Regelungen, Experten-Aussagen
    - FORMAT: laut *Quellenname*, so *Quellenname* berichtet, wie *Quellenname* meldet

   ANFÜHRUNGSZEICHEN-VERBOT:
    - NIEMALS Anführungszeichen um Inhalte setzen, die im Original keine haben
    - Indirekte Rede bleibt OHNE Anführungszeichen
    - NUR echte Direktzitate aus den Quellen in Anführungszeichen

2. QUELLENVERTEILUNG:
    - Verfügbare Quellen: {', '.join(available_sources) if available_sources else 'Finanztip, Stiftung Warentest, ifo Institut, Handelsblatt, Bild, Zeit'}
    - ALLE Quellennamen immer kursiv: *Finanztip*, *Handelsblatt*, *ifo Institut*, *Bild*, *Zeit*
    - VARIATION PFLICHT - verwende unterschiedliche Formulierungen: laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | so *Quelle*
    - NIEMALS die gleiche Formulierung zweimal verwenden!
    - Balance: Wichtige Fakten MIT Quelle, Allgemeinwissen OHNE Quelle

VERFÜGBARE ECHTE ZITATE AUS DEM ORIGINALTEXT:
{chr(10).join([f'• "{quote}" (direkte Aussage)' for quote in real_quotes[:5]]) if real_quotes else '• Keine direkten Zitate im Originaltext gefunden - verwende nur indirekte Rede'}

    ZITAT-VERWENDUNGSREGELN:
    - Verwende die oben aufgelisteten Zitate WÖRTLICH
    - Jedes verwendete Zitat MUSS mit der korrekten Quelle versehen werden
    - Format: „Zitat hier", so *Quellenname*
    - Falls keine direkten Zitate verfügbar: NUR indirekte Rede im Konjunktiv I
    - ALLE Zitate müssen ins Deutsche übersetzt werden

VERFÜGBARE FAKTEN:
{chr(10).join([f'• {fact[:100]}...' for fact in concrete_facts[:5]]) if concrete_facts else '• Nutze nur Fakten aus dem bereitgestellten Originaltext'}

ERKANNTE KATEGORIE: {primary_module} ({module_info['name']})
KATEGORIE-FOKUS: {module_info['focus']}

    LIFESTYLE/VERBRAUCHER-STIL (sachlich aber zugänglich):
    - TONALITÄT: Sachlich und informativ, aber verständlich und nicht trocken
    - KEINE Promipool-Dramatik: Vermeide emotionale Übertreibungen und Reißer-Sprache
    - KEINE Business Punk-Härte: Vermeide zu aggressive oder provokante Formulierungen
    - STATTDESSEN: Klare, direkte Sprache mit Fokus auf praktischen Nutzen
    - Verwende Formulierungen wie: "Das sollten Verbraucher wissen", "Das bedeutet konkret", "Experten raten"
    - Nutze abwechslungsreiche Quellenangaben: laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet
    - Balance: Pro Absatz maximal 1-2 strategische Quellenangaben
    - WICHTIG: Seriös und vertrauenswürdig bleiben - Verbraucher brauchen verlässliche Informationen!

    VERBRAUCHER-FOKUSSIERTE SPRACHE:
    - "Das bedeutet für Verbraucher", "Was Rentner jetzt wissen müssen", "Diese Rechte haben Sie"
    - "Darauf sollten Sie achten", "Das können Betroffene tun", "So gehen Sie vor"
    - Vermeide Fachchinesisch - erkläre Fachbegriffe kurz und verständlich
    - Nutze konkrete Beispiele und praktische Tipps

    ANTI-KI-STIL REGELN:
    - VERMEIDE: "Person, die bekannte...", "Person, bekannt aus..."
    - RICHTIG: "Expertin Name" oder "Verbraucherschützer Name"
    - VERMEIDE KI-Floskeln: "könnte der Wendepunkt sein", "sorgt für Aufsehen"
    - NUTZE stattdessen: "bringt Veränderungen", "ist relevant für", "betrifft"

    QUELLENNUTZUNG MIT FINGERSPITZENGEFÜHL:
    - Verfügbare Quellen: {', '.join([f'*{source}*' for source in available_sources])}
    - ZIEL: Alle Quellen verwenden, aber organisch und lesbar verteilt
    - BALANCE: Pro Absatz maximal 1-2 strategische Quellenangaben
    - VARIATION PFLICHT: Jede Quelle mit unterschiedlicher Formulierung:
    * laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | so *Quelle*
    - WANN zitieren: Bei wichtigen Fakten, Rechts-Infos, Zahlen, Experten-Aussagen
    - WANN NICHT: Bei Übergängen, Erklärungen, Allgemeinwissen
    - NATÜRLICHER FLUSS wichtiger als Quellenanzahl!

    QUELLENANGABEN-BALANCE (Fingerspitzengefühl):
    - NICHT jeder Satz braucht eine Quelle - das wirkt überladen!
    - PRO ABSATZ: Maximal 1-2 strategische Quellenangaben
    - ZITATE: Jedes echte Zitat braucht SOFORT eine Quellenangabe
    - FAKTEN: Wichtige Daten/Zahlen mit Quelle, aber nicht übertreiben
    - NATÜRLICHER FLUSS: Quelle dort einfügen, wo sie organisch passt
    - **ALLE QUELLENNAMEN IMMER KURSIV**: *ifo Institut*, *Handelsblatt*, *Finanztip*, *Bild*, *Zeit*
    - **NIEMALS ohne Sternchen**: "laut dem ifo Institut" ist FALSCH → "laut *ifo Institut*" ist RICHTIG

{source_info}

VERBRAUCHER-QUELLENTEXT:
{article_text}

KRITISCHE ERINNERUNG:
- JEDES Zitat braucht SOFORT eine Quellenangabe
- Pro Absatz EINE strategische Quellenangabe bei wichtigen Fakten
- Qualität vor Quantität bei Quellenangaben
- ALLE Zitate müssen ins Deutsche übersetzt werden
- Fokus auf praktischen Nutzen für Verbraucher

Erstellen Sie einen SEO-optimierten, verbraucherfreundlichen Artikel, der Informationen aus dem Artikelentwurf zusammenfasst. Behalten Sie beim Umschreiben alle Fakten und Daten bei und verwenden Sie klare, verständliche Sprache.

Wichtig: Direkte Zitate müssen exakt übernommen werden. ALLE ZITATE MÜSSEN INS DEUTSCHE ÜBERSETZT WERDEN."""

    if custom_instructions.strip():
        base_prompt += f"\n\nWICHTIG: Zusätzliche spezifische Anweisungen:\n{custom_instructions}"

    complete_prompt = base_prompt + f"""
    🚨 KRITISCH: Der Artikel muss folgende Elemente ZWINGEND enthalten:

    Titel: **PFLICHT - DARF NICHT LEER SEIN!** Entwickle einen klaren, informativen Titel (STRIKT max. 60 Zeichen - KÜRZE wenn nötig!), der das Thema auf den Punkt bringt. Der Titel soll Verbraucher direkt ansprechen, relevante Keywords enthalten und zur {module_info['name']}-Kategorie passen. Vermeide übertriebene Dramatik - Klarheit und Relevanz stehen im Vordergrund.

    **🚨 KRITISCH: Titel darf NICHT länger als 60 Zeichen sein! Lieber kürzer und prägnant als zu lang!**

    **BEISPIELE für gute Titel (alle unter 60 Zeichen):**
    - "Deutsche Industrie: Wettbewerbsfähigkeit auf Tiefpunkt" (54 Zeichen)
    - "Google investiert 5 Milliarden in deutsche Infrastruktur" (57 Zeichen)
    - "Wettbewerbsfähigkeit sinkt: Industrie alarmiert" (48 Zeichen)

    Untertitel: **PFLICHT - DARF NICHT LEER SEIN!** Formuliere einen prägnanten Untertitel mit MAXIMAL 3-4 Wörtern (STRIKT max. 20 Zeichen)

    **BEISPIELE für gute Untertitel:**
    - "Wirtschaft unter Druck" (22 Zeichen - ok)
    - "Milliarden-Investition" (21 Zeichen - ok)
    - "Strukturelle Probleme" (22 Zeichen - ok)

    Abstract: Verfasse ein lebendiges, informatives Abstract, das den Kern des Artikels zusammenfasst, relevante Schlüsselwörter aus der {module_info['name']}-Kategorie enthält und die Relevanz des Themas zeigt.

    🚨 KRITISCHES ABSTRACT-VERBOT (UNBEDINGT BEACHTEN!):
    ❌ ABSOLUT VERBOTEN - Diese Formulierungen NIEMALS verwenden:
       • "Der Artikel..." (bietet/beleuchtet/erklärt/zeigt/behandelt)
       • "Dieser Text..." / "Dieser Beitrag..."
       • "Im Folgenden..." / "Nachfolgend..."
       • "Hier erfahren..." / "Sie erfahren..." / "Erfahren Sie..."
       • "Entdecken Sie..." / "Lernen Sie..."

    ⚠️ WARUM VERBOTEN? Diese Formulierungen sprechen ÜBER den Artikel statt DIREKT INS THEMA zu gehen!

    ✅ STATTDESSEN - SO MUSS DAS ABSTRACT SEIN:
    - Direkt mit dem Thema starten (NICHT über den Artikel reden!)
    - Sachlich, lebendig und konkret
    - Fokus auf praktischen Nutzen (ohne "Sie" zu verwenden)
    - Nenne konkret, was behandelt wird (Freibeträge, Regeln, Strategien, Tipps)
    - KEINE Spoiler bei konkreten Zahlen
    - BALANCE: Genug Info für Relevanz, Details für Haupttext

    ABSTRACT BEISPIELE - GENAU SO SCHREIBEN:
    ✅ PERFEKT: "Witwenrente und Nebenverdienst müssen nicht im Widerspruch stehen. Welche Freibeträge gelten, wie verschiedene Einkommensarten angerechnet werden und welche Strategien die Rente optimieren."
    ✅ PERFEKT: "Relevante Freibeträge, Anrechnungsregeln und Strategien zur Optimierung der Witwenrente im Überblick."

    ❌ ABSOLUT FALSCH: "Der Artikel bietet wertvolle Informationen..."
    ❌ ABSOLUT FALSCH: "Der Artikel beleuchtet relevante Freibeträge..."
    ❌ ABSOLUT FALSCH: "Erfahren Sie, wie Sie Einkommensarten kombinieren..."

    🚨 NOCHMAL: NIEMALS "Der Artikel..." oder "Sie/Erfahren Sie" verwenden!

    Artikeltext: Der Artikel soll ausführlich, detailliert und informativ sein (MINDESTENS 500-600 Wörter).

    AUSFÜHRLICHKEITS-REGELN:
    - Verarbeite ALLE Details aus den Quellen - nichts weglassen!
    - Schreibe ausführlich, nicht zusammenfassend
    - Jeder Absatz sollte 100-120 Wörter umfassen (lieber mehr!)
    - Füge Kontext und Hintergründe hinzu
    - Füge beschreibende Details hinzu (Zahlen, Experten-Meinungen, Positionen, Beispiele)
    - Nutze konkrete Beschreibungen für Personen (Name + Position + Organisation)
    - Entwickle jeden Aspekt in 2-3 Sätzen, nicht nur in einem
    - Nutze Zitate aus den Quellen für mehr Tiefe

    STRUKTUR-ANFORDERUNGEN:
    - Erstelle 5 Absätze mit passenden ### Zwischenüberschriften
    - Der erste Absatz (Einstieg) bekommt keine Zwischenüberschrift
    - Jeder Absatz sollte 100-120 Wörter umfassen
    - Verarbeite alle relevanten Informationen aus den Quellen

    BEISPIEL-STRUKTUR:
    1. Einstiegs-Absatz ohne Überschrift (100-120 Wörter)
    2. ### [Erste Zwischenüberschrift] (100-120 Wörter)
    3. ### [Zweite Zwischenüberschrift] (100-120 Wörter)
    4. ### [Dritte Zwischenüberschrift] (100-120 Wörter)
    5. ### [Vierte Zwischenüberschrift] (100-120 Wörter)
    6. ### [Fünfte Zwischenüberschrift] (100-120 Wörter)

    WICHTIGE REGELN FÜR DEN ARTIKELTEXT:
    - 🚨 **KRITISCH: Übernimm ALLE wichtigen Informationen aus dem Quelltext - NICHTS weglassen!**
    - Nutze konkrete Zahlen, Beträge und Prozentsätze **wenn sie im Quelltext vorhanden sind**
    - **PFLICHT: Bei konkreten Zahlen, Beträgen und Fakten IMMER Quellenangabe kursiv: *Merkur*, *Finanztip* etc.**
    - Füge praktische Beispiele ein **basierend auf dem Quelltext**:
      * Bei Finanz-Themen: Rechenbeispiele wie "Das bedeutet konkret: Bei 1.500 Euro..."
      * Bei Lifestyle-Themen: Praktische Tipps und Handlungsempfehlungen
      * Bei Gesundheits-Themen: Konkrete Anwendungsfälle
    - Strukturiere den Text in mehrere Absätze mit passenden Zwischenüberschriften
    - Der erste Absatz benötigt keine Zwischenüberschrift
    - KEINE TABELLEN - wandle Tabellen-Informationen in Fließtext um
    - Verwende klare, verständliche Sprache
    - Fokussiere auf praktischen Nutzen für Verbraucher

    📋 DETAIL-CHECKLISTE (alles muss im Artikel vorkommen, wenn im Quelltext vorhanden):
    ✅ Alle Zahlen, Beträge, Prozentsätze (mit Quellenangabe!)
    ✅ Alle Fristen, Stichtage, Zeiträume (z.B. "jährlich zum 1. Juli")
    ✅ Alle Sonderregelungen (z.B. "Sterbevierteljahr", "Freibeträge pro Kind")
    ✅ Alle Einkommensarten die ANGERECHNET werden (mit konkreten Prozentsätzen!)
    ✅ Alle Einkommensarten die NICHT angerechnet werden (z.B. Riester, Wohngeld)
    ✅ Alle praktischen Tipps und Strategien aus dem Quelltext
    ✅ Alle Kontaktstellen, Beratungsangebote, Ansprechpartner (wenn genannt)
    ✅ Alle rechtlichen Grundlagen, Gesetzesänderungen, Neuregelungen

    QUELLENANGABEN IM ARTIKELTEXT (CLUSTER-SYSTEM für Lesbarkeit):
    - **CLUSTER-REGEL**: Mehrere zusammenhängende Zahlen mit EINER Quellenangabe abdecken
    - Pro **Absatz** oder **Themenblock** mindestens 1 Quellenangabe bei wichtigen Fakten
    - NICHT bei jeder einzelnen Zahl (wird repetitiv), ABER auch nicht zu selten (Credibility!)

    **CLUSTER-BEISPIELE (elegant):**
    ✅ "Seit Juli 2025 liegt der Freibetrag bei 1.076,86 Euro, der sich um 228,42 Euro pro Kind erhöht, wie *Merkur* berichtet."
    ✅ "Die Anrechnung variiert je nach Einkommensart, so *Merkur*: Bei Arbeitseinkommen 40%, bei Selbstständigkeit 39,80%, bei Beamten 27,50% und bei Kapital 25%."
    ✅ "Laut *Finanztip* wird das Einkommen jährlich zum 1. Juli überprüft, wobei der Bruttoverdienst des Vorjahres herangezogen wird."

    ❌ NICHT SO (zu repetitiv):
    "... 1.076 Euro, wie *Merkur* berichtet. Pro Kind 228 Euro, so *Merkur*. Bei Überschreitung 40%, laut *Merkur*..."

    **FORMAT-VARIATIONEN:**
    - "... wie *Quelle* berichtet" | "so *Quelle*" | "laut *Quelle*" | "heißt es bei *Quelle*"

    BEISPIEL für Tabellen-Umwandlung in Fließtext:
    "Bei Arbeitseinkommen werden pauschal 40 Prozent abgezogen, bei Selbstständigkeit 39,80 Prozent, bei Beamtenbezügen 27,50 Prozent und bei Kapitalvermögen 25 Prozent."

    Metabeschreibung: Füge eine prägnante Metabeschreibung hinzu (150-160 Zeichen), die den Inhalt zusammenfasst und zum Klicken animiert.

    METABESCHREIBUNG REGELN:
    - KEINE direkte Ansprache mit "Sie", "Erfahren Sie", "Entdecken Sie", "Lernen Sie"
    - STATTDESSEN: Sachlich, konkret und informativ
    - Fokus auf Nutzen und Inhalt ohne persönliche Anrede
    - Format: Stichwortartig oder als sachliche Aussage

    METABESCHREIBUNG BEISPIELE:
    ✅ GUT: "Witwenrente optimal nutzen: Freibeträge, Anrechnungsregeln und praktische Strategien zur Einkommensoptimierung. Alle wichtigen Infos im Überblick."
    ✅ GUT: "Freibeträge bei Witwenrente: Welche Einkommensarten angerechnet werden und wie Betroffene ihre Rente clever optimieren können."
    ❌ SCHLECHT: "Entdecken Sie, wie Sie Ihre Witwenrente optimieren können. Erfahren Sie alles über Freibeträge und Anrechnungsarten."

    Bitte beachte: Der Artikel soll sachlich und verbraucherfreundlich sein, ohne Leser direkt anzusprechen. Vermeide Schlusswort oder Fazit.

    Besonderheiten:
    Alle verwendeten Zitate müssen wörtlich übernommen werden.
    Übersetze Zitate immer in deutsche Sprache.
    Setze immer die Kombination aus Vor- und Nachname.
    PFLICHT: Erwähne ALLE wichtigen Personen mit Position und Organisation (z.B. "Finanzminister Lars Klingbeil (SPD)", "Ökonom Stefan Bach vom DIW")
    WICHTIG: Wenn Politiker, Minister oder Regierungsvertreter in den Quellen erwähnt werden, müssen diese mit Position und Partei im Artikel erscheinen
    Verwende alle relevanten Informationen aus den Entwurfsquellen - nichts weglassen!
    Verwende korrekte Quellenangaben kursiv: *Finanztip*, *Stiftung Warentest*, *Merkur*
    Fokussiere auf praktischen Nutzen für Verbraucher mit konkreten Beispielen
    Nutze verfügbare Zitate aus den Quellen für mehr Substanz

    Checkliste (vor dem Absenden prüfen!):
    ✅ **KRITISCH: Ist der TITEL ausgefüllt, NICHT leer und MAX. 60 Zeichen?** (Ohne Titel kann der Artikel NICHT an die API gesendet werden!)
    ✅ **KRITISCH: Ist der UNTERTITEL ausgefüllt, NICHT leer und MAX. 20 Zeichen?**
    ✅ Ist der Artikeltext MINDESTENS 500 Wörter lang? (Besser 550-600!)
    ✅ Hat der Artikel 5 Absätze mit Zwischenüberschriften (außer dem ersten)?
    ✅ Hat jeder Absatz 100-120 Wörter (lieber mehr als weniger)?
    ✅ Wurden ALLE wichtigen Personen mit Position und Organisation erwähnt? (z.B. Finanzminister + Name + Partei)
    ✅ Wurden ALLE Zitate aus den Quellen verwendet?
    ✅ Wurden ALLE wichtigen Details verarbeitet (nichts ausgelassen)?
    ✅ Sind alle Zitate korrekt ins Deutsche übersetzt?
    ✅ Sind die Zitate unverändert übernommen worden?
    ✅ Ist überall Vor- und Nachname gesetzt worden?
    ✅ Sind ALLE relevanten Informationen aus dem Quelltext übernommen worden (nichts ausgelassen)?
    ✅ **KRITISCH: Sind ALLE Quellenangaben MIT STERNCHEN kursiv? (*ifo Institut*, *Handelsblatt*)**
    ✅ **KRITISCH: Gibt es KEINE Quellenangaben ohne Sternchen? ("laut dem ifo Institut" ist FALSCH!)**
    ✅ Ist der Ton sachlich aber zugänglich (nicht zu dramatisch, nicht zu trocken)?
    ✅ Enthält das Abstract KEINE Meta-Formulierungen ("Der Artikel...")?
    ✅ Enthält die Metabeschreibung KEINE direkte Ansprache ("Sie", "Erfahren Sie")?

    🚨 KRITISCH: Der Artikel muss die folgenden Komponenten ZWINGEND beinhalten und genau so formatiert sein:

    Titel:
    [Dein konkreter Titel HIER - DARF NICHT LEER SEIN! STRIKT max. 60 Zeichen - lieber kürzer!]

    Untertitel:
    [Dein Untertitel HIER - DARF NICHT LEER SEIN! STRIKT max. 20 Zeichen, 3-4 Wörter]

    Abstract:
    [Dein Abstract ohne Anführungszeichen und ohne Formatierung]

    Artikeltext:
    [Hier kommt der Haupttext ohne Bulletpoints]

    ### [Erste Zwischenüberschrift]
    [Textabsatz mit korrekten Quellenangaben]

    ### [Zweite Zwischenüberschrift]
    [Textabsatz mit korrekten Quellenangaben]

    Formatierungsregeln:
    - Verwende ### für Zwischenüberschriften (WICHTIG: Genau drei Hashzeichen)
    - Lasse immer eine Leerzeile zwischen Absätzen
    - Keine Sternchen (*) für Formatierung außer bei Quellenangaben
    - Keine Anführungszeichen außer bei direkten Zitaten
    - Keine Zwischenüberschrift vor dem ersten Absatz
    - Quellen IMMER KURSIV: *ifo Institut* (mit einfachen Sternchen)
    - NIEMALS Quellen in Anführungszeichen: "ifo Institut" ist FALSCH
    - NIEMALS Quellen ohne Sternchen: "laut dem ifo Institut" ist FALSCH
    - RICHTIG: laut *ifo Institut*, so *Handelsblatt* berichtet, wie *Finanztip* meldet

    Metabeschreibung:
    [Deine Metabeschreibung]

    Keywords:
    [Deine Keywords OHNE Hashtags, nur Begriffe kommagetrennt, z.B.: {', '.join([tag.replace('#', '') for tag in module_info['hashtags'][:3]])}, relevante Themenbegriffe]

    Hier ist der Text des Entwurfsartikels: {article_text}"""

    result = generate_text(complete_prompt)
    result = convert_source_quotes_to_german(result)
    return result

def process_text_for_video_article_long(result_text: str, source_info: str = "") -> str:
    """
    Generiert einen langen Video-Artikel OHNE Zwischenüberschriften, mit starkem Hook am Anfang
    NUR Headline (KEIN Untertitel), mit Hashtags am Ende
    """
    prompt = f"""Erstelle einen ausführlichen Video-Artikel für Lifestyle/Verbraucher-Content basierend auf dem generierten Artikel.

📹 FORMAT: Video-Artikel Lang
📝 STRUKTUR: NUR Headline + Fließtext OHNE Zwischenüberschriften (###)
🎯 HOOK: Starker Einstieg mit Zahl/Betrag in den ersten 8-12 Worten
#️⃣ HASHTAGS: Am Ende des Artikels

🎣 HOOK-REGEL (KRITISCH!):
- Die ersten 2 Sätze müssen wie ein starker Hook funktionieren
- PFLICHT: Konkrete Zahl, Betrag oder Anzahl in den ersten 8-12 Worten
- Schockierend, überraschend oder dringend

🔥 HOOK-FORMELN (sachlich aber stark):
1. **Konkrete Zahlen/Datum + Sachinfo**: "Ab 2026: [Maßnahme] betrifft [Millionen] Deutsche"
2. **Betrag + Relevanz**: "[Betrag] mehr: Diese Steuererhöhung kommt"
3. **Experten-Warnung**: "Ökonom warnt: [Konkrete Auswirkung]"
4. **Mehrwertsteuer-Schock**: "Mehrwertsteuer steigt: [Konkrete Folge]"
5. **Zahlen-basiert**: "[Prozent/Millionen] betroffen: [Was kommt]"

✅ PERFEKTE HOOK-BEISPIELE (sachlich-neutral):
  * "Ab 2026: Steuererhöhungen treffen deutsche Steuerzahler"
  * "Mehrwertsteuer steigt: Das zahlen Verbraucher mehr"
  * "Finanzminister plant: 1% Vermögensteuer ab 25 Millionen Euro"
  * "Ökonom warnt: Sozialleistungen könnten gekürzt werden"

❌ VERMEIDE (zu reißerisch):
  * "Achtung: Steuererhöhungen kosten Milliarden!" (zu alarmistisch)
  * "Steuerzahler aufgepasst!" (zu Boulevard)
  * "Krass: Hier zahlen Deutsche drauf!" (zu BILD-Stil)

📊 ARTIKEL-STRUKTUR:
1. **Hook-Absatz** (2-3 Sätze): Starker Einstieg mit Zahl/Betrag
2. **Hauptteil** (4-6 Absätze): Alle wichtigen Informationen aus dem Original-Artikel
3. **Praktische Details**: Konkrete Zahlen, Beispiele, Regelungen
4. **Abschluss**: Wichtigster Takeaway oder Handlungsempfehlung
5. **Hashtags** (3-5 relevante Tags am Ende)

🎨 WICHTIGE FORMATIERUNGS-REGELN:
- **NUR Headline** - KEIN Untertitel, KEIN Abstract
- **KEINE Zwischenüberschriften (###)** - nur Fließtext mit Absätzen
- **KEINE Bulletpoints** - alles in Satzform
- **Leerzeilen zwischen Absätzen** für bessere Lesbarkeit
- **Absatzlänge**: 3-5 Sätze pro Absatz

🔗 QUELLENANGABEN (KRITISCH - STRIKT BEFOLGEN):
- **ALLE Quellennamen IMMER KURSIV**: *ifo Institut*, *Finanztip*, *Stiftung Warentest*, *Handelsblatt*
- **FORMAT**: laut *Quelle*, *Quelle* berichtet, wie *Quelle* meldet, so *Quelle*
- **BEISPIELE**: laut *ifo Institut*, so *Handelsblatt* berichtet, wie *Finanztip* meldet
- **NIEMALS** Quellenangaben ohne Sternchen: "so das ifo Institut" ist FALSCH
- **RICHTIG**: "so *ifo Institut*" oder "laut *ifo Institut*"
- **SPARSAM verwenden**: 2-3 Quellenangaben im gesamten Artikel
- NUR bei wichtigen Fakten, Zahlen oder direkten Zitaten

📏 LÄNGE:
- Optimal: 150-180 Wörter
- 3-4 Absätze (kompakt aber ausführlich!)
- Fokus auf das Wichtigste - alle wichtigen Infos rein (Personen, Zahlen, Maßnahmen)

#️⃣ HASHTAGS (am Ende des Artikels):
- 3-5 relevante Hashtags
- Kategoriebasiert: #wirtschaft #industrie #rente #finanzen #verbraucher #gesundheit #wohnen #lifestyle
- Format: Am Ende nach einer Leerzeile

🎨 TONALITÄT (NEUTRAL - KEIN SIEZEN, KEIN DUZEN):
- Informativ und sachlich
- KEINE direkte Ansprache mit "Sie" oder "Du"
- STATTDESSEN: "Rentner können", "Betroffene sollten", "Verbraucher haben Anspruch"
- Fokus auf praktischen Nutzen ohne persönliche Anrede
- Verständliche, neutrale Sprache

✅ GUTE FORMULIERUNGEN (neutral):
  * "Rentner können bis zu 1.076 Euro hinzuverdienen"
  * "Betroffene sollten die Regelungen kennen"
  * "Wer die Freibeträge nutzt, profitiert"
  * "Das bedeutet konkret für Witwenrentner"
  * "Wichtig: Nicht alle Einkommensarten werden angerechnet"

❌ SCHLECHTE FORMULIERUNGEN (zu direkt):
  * "Sie können bis zu 1.076 Euro hinzuverdienen" → ZU FORMELL
  * "Du kannst bis zu 1.076 Euro hinzuverdienen" → ZU INFORMELL
  * "Nutzen Sie den Freibetrag" → DIREKTES SIEZEN
  * "Hol dir den Freibetrag" → DIREKTES DUZEN

⚡ KRITISCH - CHECKLISTE:
- ✅ Der Hook ist das Wichtigste!
- ✅ KEINE ### Überschriften verwenden
- ✅ KEIN Untertitel, KEIN Abstract
- ✅ Alle wichtigen Infos aus dem Original übernehmen
- ✅ **QUELLENANGABEN IMMER KURSIV**: *ifo Institut*, *Handelsblatt*, *Finanztip*
- ✅ **NIEMALS** Quellen ohne Sternchen: "das ifo Institut" ist FALSCH!
- ✅ Hashtags am Ende anfügen
- ✅ Metabeschreibung hinzufügen

BEISPIEL-STRUKTUR (150-180 Wörter, neutrale Tonalität):

Headline: Witwenrente und Nebenverdienst: 1.076 Euro Freibetrag

Artikeltext:
Rentner aufgepasst: 1.076 Euro Freibetrag nutzen! Diese Summe können Witwenrentner seit Juli 2025 hinzuverdienen, ohne dass ihre Rente gekürzt wird.

Die Deutsche Rentenversicherung hat die Freibeträge angepasst. Das bedeutet konkret: Wer Witwenrente bezieht und nebenbei arbeitet, kann bis zu diesem Betrag verdienen. Pro Kind erhöht sich der Freibetrag um weitere 228,42 Euro, wie *Merkur* berichtet.

Bei Überschreitung wird das Einkommen angerechnet. Die Anrechnung variiert je nach Einkommensart: Bei Arbeitseinkommen werden 40 Prozent angerechnet, bei Selbstständigkeit 39,80 Prozent. Laut *Finanztip* erfolgt die Überprüfung jährlich zum 1. Juli.

Wichtig: Nicht alle Einkommensarten werden angerechnet. Riester-Rente, Wohngeld und Kindergeld bleiben außen vor. Wer die Freibeträge kennt, kann Rente und Nebenverdienst optimal kombinieren.

Metabeschreibung: Witwenrente optimal nutzen: Freibeträge, Anrechnungsregeln und praktische Strategien zur Einkommensoptimierung. Alle wichtigen Infos im Überblick.

#rente #altersvorsorge #finanzen #verbraucher #geldtipps

---

Original-Artikel:
{result_text}

Erstelle jetzt den Video-Artikel Lang mit starkem Hook, Metabeschreibung und Hashtags:

Headline:
[Knackige Headline - max. 60 Zeichen]

Artikeltext:
[Fließtext OHNE ### Überschriften, mit Hook am Anfang]

Metabeschreibung:
[Prägnante Metabeschreibung, 150-160 Zeichen, sachlich ohne "Sie"/"Du"]

[Hashtags am Ende]"""

    return generate_text(prompt)

def process_text_for_video_article_short(result_text: str, source_info: str = "") -> str:
    """
    Generiert einen kurzen Video-Artikel (kompakt, auf das Wesentliche reduziert)
    NUR Headline (KEIN Untertitel), mit starkem Hook und Hashtags
    """
    prompt = f"""Erstelle einen kurzen, kompakten Video-Artikel für Lifestyle/Verbraucher-Content basierend auf dem generierten Artikel.

📹 FORMAT: Video-Artikel Kurz (Kompaktversion)
📝 STRUKTUR: NUR Headline + 2-3 kurze Absätze, auf das Wesentliche reduziert
🎯 HOOK: Starker Einstieg mit Zahl/Betrag im ersten Satz
#️⃣ HASHTAGS: Am Ende des Artikels

🎣 HOOK-REGEL (KRITISCH!):
- Der erste Satz MUSS wie ein starker Hook funktionieren
- PFLICHT: Konkrete Zahl, Betrag oder Anzahl in den ersten 8-12 Worten
- Schockierend, überraschend oder dringend

🔥 HOOK-FORMELN (sachlich-neutral):
1. **Konkrete Zahlen/Datum + Sachinfo**: "Ab 2026: [Maßnahme]"
2. **Betrag + Relevanz**: "[Betrag]: [Was kommt]"
3. **Experten-Statement**: "Ökonom: [Konkrete Aussage]"

✅ PERFEKTE HOOK-BEISPIELE (sachlich-neutral):
  * "Ab 2026: Steuererhöhungen für deutsche Steuerzahler"
  * "Mehrwertsteuer steigt: Verbraucher zahlen mehr"
  * "1% Vermögensteuer ab 25 Millionen Euro geplant"

❌ VERMEIDE (zu reißerisch):
  * "Achtung: Steuererhöhungen ab 2026!" (zu alarmistisch)
  * "1.076 Euro geschenkt!" (zu werblich)

📊 ARTIKEL-STRUKTUR:
1. **Hook-Absatz** (2-3 Sätze): Starker Einstieg mit Zahl/Betrag + Kern der Info
2. **Hauptinfo-Absatz** (2-3 Sätze): Die wichtigsten Fakten kompakt
3. **Takeaway-Absatz** (1-2 Sätze): Wichtigster Punkt zum Mitnehmen
4. **Hashtags** (3-5 relevante Tags am Ende)

🎨 FORMATIERUNG:
- **NUR Headline** - KEIN Untertitel, KEIN Abstract
- **2-3 kurze Absätze** - auf das Wesentliche reduziert
- **Keine Überschriften im Text**
- **Kurze, prägnante Sätze**

🔗 QUELLENANGABEN (KRITISCH - STRIKT BEFOLGEN):
- **ALLE Quellennamen IMMER KURSIV**: *ifo Institut*, *Finanztip*, *Stiftung Warentest*, *Handelsblatt*
- **FORMAT**: laut *Quelle*, *Quelle* berichtet, wie *Quelle* meldet, so *Quelle*
- **BEISPIELE**: laut *ifo Institut*, so *Handelsblatt* berichtet, wie *Finanztip* meldet
- **NIEMALS** Quellenangaben ohne Sternchen: "so das ifo Institut" ist FALSCH
- **RICHTIG**: "so *ifo Institut*" oder "laut *ifo Institut*"
- **SPARSAM verwenden**: 1-2 Quellenangaben im Artikel (wegen Kürze)
- NUR bei den wichtigsten Fakten

📏 LÄNGE:
- Insgesamt 100-120 Wörter
- Kompakt - nur die wichtigsten Infos
- Personen mit Position, Zahlen, Kernmaßnahmen erwähnen

#️⃣ HASHTAGS (am Ende des Artikels):
- 3-5 relevante Hashtags
- Kategoriebasiert: #wirtschaft #industrie #rente #finanzen #verbraucher #gesundheit #wohnen #lifestyle
- Format: Am Ende nach einer Leerzeile

🎨 TONALITÄT (NEUTRAL - KEIN SIEZEN, KEIN DUZEN):
- Informativ und direkt
- KEINE direkte Ansprache mit "Sie" oder "Du"
- STATTDESSEN: "Rentner können", "Betroffene sollten", "Wer ... kann"
- Fokus auf das Wichtigste ohne persönliche Anrede
- Verständliche, neutrale Sprache
- Keine Redundanzen!

✅ GUTE FORMULIERUNGEN (neutral):
  * "Rentner können hinzuverdienen"
  * "Betroffene sollten beachten"
  * "Wer die Freibeträge nutzt, profitiert"
  * "Wichtig für Witwenrentner"

❌ SCHLECHTE FORMULIERUNGEN (zu direkt):
  * "Sie können hinzuverdienen" → ZU FORMELL
  * "Du kannst hinzuverdienen" → ZU INFORMELL

⚡ KRITISCH - CHECKLISTE:
- ✅ Der Hook im ersten Satz ist das Wichtigste!
- ✅ Nur die essentiellen Infos - keine Details
- ✅ KEIN Untertitel, KEIN Abstract
- ✅ Extrem kompakt und auf den Punkt
- ✅ **QUELLENANGABEN IMMER KURSIV**: *ifo Institut*, *Handelsblatt*, *Finanztip*
- ✅ **NIEMALS** Quellen ohne Sternchen: "das ifo Institut" ist FALSCH!
- ✅ Hashtags am Ende
- ✅ Metabeschreibung hinzufügen
- ✅ Neutrale Sprache ohne direkte Anrede

BEISPIEL (neutrale Tonalität):

Headline: Witwenrente: 1.076 Euro Freibetrag

Artikeltext:
Rentner aufgepasst: 1.076 Euro Freibetrag! Diese Summe können Witwenrentner seit Juli 2025 hinzuverdienen, ohne dass die Rente gekürzt wird. Pro Kind erhöht sich der Betrag um weitere 228,42 Euro, wie *Merkur* berichtet.

Bei Überschreitung wird das Einkommen je nach Art unterschiedlich angerechnet – bei Arbeitseinkommen 40 Prozent, bei Selbstständigkeit 39,80 Prozent. Laut *Finanztip* bleiben Riester-Rente, Wohngeld und Kindergeld außen vor.

Wer die Regelungen kennt, kann Rente und Nebenverdienst optimal kombinieren. Die Überprüfung erfolgt jährlich zum 1. Juli.

Metabeschreibung: Witwenrente und Nebenverdienst: Freibeträge, Anrechnungsregeln und wichtige Informationen zur Einkommensoptimierung kompakt erklärt.

#rente #altersvorsorge #finanzen #verbraucher #geldtipps

---

Original-Artikel:
{result_text}

Erstelle jetzt den Video-Artikel Kurz - extrem kompakt mit starkem Hook, Metabeschreibung und Hashtags:

Headline:
[Knackige Headline - max. 60 Zeichen]

Artikeltext:
[2-3 kurze Absätze mit Hook am Anfang, nur das Wesentliche]

Metabeschreibung:
[Prägnante Metabeschreibung, 150-160 Zeichen, sachlich ohne "Sie"/"Du"]

[Hashtags am Ende]"""

    return generate_text(prompt)

def extract_video_article_components(article_result: str) -> tuple:
    """
    Extrahiert Headline, Artikeltext, Metabeschreibung und Hashtags aus Video-Artikel
    """
    headline_pattern = r"Headline:\s*(.*?)\n+"
    meta_pattern = r"Metabeschreibung:\s*(.*?)\n+(?:#|\Z)"

    headline = re.search(headline_pattern, article_result, re.DOTALL)
    meta = re.search(meta_pattern, article_result, re.DOTALL)

    # Extract content
    content = article_result
    if headline:
        content = re.sub(headline_pattern, "", content, flags=re.DOTALL).strip()

    # Remove "Artikeltext:" label
    content = re.sub(r"Artikeltext:\s*\n*", "", content, flags=re.MULTILINE)

    # Remove Metabeschreibung from content
    if meta:
        content = re.sub(r"Metabeschreibung:.*?(?:\n+#|\Z)", "", content, flags=re.DOTALL).strip()

    content = content.strip()

    clean_headline = headline.group(1).strip() if headline else ""
    clean_meta = meta.group(1).strip() if meta else ""

    return clean_headline, content, clean_meta

# ALTE SCRIPT-FUNKTIONEN ENTFERNT - Nicht mehr benötigt
# process_text_for_video_script_short() - gelöscht
# process_text_for_video_script_long() - gelöscht

def OLD_process_text_for_video_script_short(result_text):
    """
    VERALTET - Generiert kurzes TikTok-Script (40 Sek., ca. 75-85 Worte) nach Promipool TikTok Playbook
    Diese Funktion wird nicht mehr verwendet - Video-Artikel ersetzen die Scripts
    """
    prompt = f"""Erstelle ein kurzes TikTok-Video-Script für Lifestyle/Verbraucher-Content basierend auf dem Artikeltext.

📹 FORMAT: TikTok-optimiertes Video-Script
⏱️ LÄNGE: 40 Sekunden (ca. 75-85 Worte)
🎯 PLATTFORM: TikTok (9:16 Vertical, schnelle Schnitte)

🎣 HOOK-REGEL (KRITISCH - HÖCHSTE PRIORITÄT!):
- Die ersten 2 SEKUNDEN = erste 8-12 Worte = ALLES!
- PFLICHT: Konkrete Zahl, Betrag oder Anzahl in den ersten 8-12 Worten!
- Hook-Qualität wichtiger als exakte Wortanzahl (72 vs 75-85 Worte ist ok bei perfektem Hook)

🔥 HOOK-FORMELN (mindestens eine nutzen):
1. **Konkrete Summe + Versprechen**: "[Betrag] geschenkt! So..."
2. **Warnung + Konkreter Verlust**: "Achtung: Dieser Fehler kostet [Betrag]!"
3. **Anzahl Betroffene + Relevanz**: "[Millionen] Menschen betroffen!"
4. **Zeitdruck + Vorteil**: "Nur noch bis [Datum]: [Betrag] sichern!"
5. **Schock-Element**: "Krass: Hier verschenken Deutsche [Betrag]!"

✅ PERFEKTE HOOK-BEISPIELE (alle mit Zahlen in ersten 8-12 Worten):
  * "1.076 Euro geschenkt! So nutzen Sie den Renten-Freibetrag!"
  * "Achtung: Dieser Fehler kostet Rentner 430 Euro monatlich!"
  * "21 Millionen Rentner betroffen – das ändert sich jetzt!"
  * "Krass: Hier verschenken Verbraucher 500 Euro pro Jahr!"
  * "Nur noch bis Dezember: So sichern Sie sich 800 Euro!"
  * "2.400 Euro Verlust! Dieser Renten-Fehler ist fatal!"

❌ SCHLECHTE HOOKS (NIEMALS SO):
  * "Vorsicht bei der Rente – das wird teuer!" → KEINE Zahl!
  * "Krass: So viel Geld verschenken die meisten!" → Zahl zu spät!
  * "Das sollten alle Rentner wissen..." → Langweilig, keine Zahl!

📊 STRUKTUR (Promipool TikTok Playbook):
1. **HOOK** (0-2 Sek., erste 8-12 Worte): Schockierender Fakt, überraschende Zahl, dringende Warnung
2. **MAIN STORY** (2-35 Sek.): Kerninfos, wichtigste Fakten, konkrete Zahlen
3. **OUTRO** (35-40 Sek.): Handlungsaufforderung oder wichtigster Takeaway

🎨 TONALITÄT (Lifestyle/Verbraucher):
- Informativ, seriös, leicht emotional
- Klare, verständliche Sprache (KEINE Slang-Begriffe)
- Sachlich aber zugänglich
- Fokus auf praktischen Nutzen: "Das bedeutet für Verbraucher", "Darauf sollten Sie achten"
- **🚨 KRITISCH: Emotionale Füllwörter EXTREM sparsam einsetzen!**
  * "Doch aufgepasst!", "Und das Beste?", "Aber Vorsicht!" → MAXIMAL 1x pro Script!
  * Bei langem Script (1:30 Min.): maximal 2x erlaubt
  * Mehr als 2x wirkt unseriös und übertrieben!
  * Übertreibungen vermeiden - Fakten sprechen für sich
  * Balance zwischen lebendig und seriös halten

  ❌ BEISPIEL FALSCH (zu viele Füllwörter):
  "1.076 Euro! Und das Beste? Pro Kind 228 Euro! Doch aufgepasst! Überschreitung = 40%..."
  → 3x Füllwörter in kurzem Script = UNSERIÖS!

  ✅ BEISPIEL RICHTIG (sparsam):
  "1.076 Euro Freibetrag! Pro Kind 228 Euro extra. Überschreitung wird zu 40% angerechnet..."
  → 0-1x Füllwörter = SERIÖS!

#️⃣ HASHTAGS (am Ende):
Füge 3-5 relevante Hashtags hinzu, z.B.:
- Für Wirtschafts-Themen: #wirtschaft #industrie #unternehmen #standort #konjunktur
- Für Renten-Themen: #rente #altersvorsorge #finanzen #verbraucher #geldtipps
- Für Verbraucher-Themen: #verbraucher #verbraucherschutz #spartipps #finanztipps #geldsparen
- Für Gesundheit: #gesundheit #krankenkasse #verbraucher #gesundheitstipps
- Für Wohnen: #miete #wohnen #mietrecht #immobilien #verbraucher

⚡ WICHTIG:
- Exakt 75-85 Worte (zähle genau!)
- KEINE Anrede, KEINE Verabschiedung
- Fließtext ohne Überschriften
- Zum Sprechen geeignet
- Der Hook ist das Wichtigste! Erste 2 Sekunden = erste 8-12 Worte!

BEISPIEL mit starkem Hook (82 Worte):
"52 Euro mehr Rente ab Januar – für Millionen Rentner! Die Bundesregierung hat eine Rentenerhöhung von 3,5 Prozent beschlossen. Das bedeutet konkret: Wer aktuell 1.500 Euro Rente bekommt, erhält künftig 52,50 Euro mehr pro Monat. Bei 2.000 Euro Rente sind es sogar 70 Euro zusätzlich. Die Auszahlung erfolgt automatisch, Rentner müssen nichts beantragen. Experten rechnen damit, dass die Erhöhung die gestiegenen Lebenshaltungskosten teilweise ausgleicht. Dennoch bleibt die Frage: Reicht das aus? #rente #rentenerhöhung #altersvorsorge #finanzen #verbraucher"

Artikel:
{result_text}

Erstelle jetzt das TikTok-Script mit starkem Hook (75-85 Worte + Hashtags):"""

    return generate_text(prompt)

def process_text_for_video_script_long(result_text):
    """
    Generiert langes TikTok-Script (1:30-1:40 Min., ca. 150-180 Worte) nach Promipool TikTok Playbook
    """
    prompt = f"""Erstelle ein ausführliches TikTok-Video-Script für Lifestyle/Verbraucher-Content basierend auf dem Artikeltext.

📹 FORMAT: TikTok-optimiertes Video-Script (Lang)
⏱️ LÄNGE: 1:30-1:40 Minuten (ca. 150-180 Worte)
🎯 PLATTFORM: TikTok (9:16 Vertical, schnelle Schnitte)

🎣 HOOK-REGEL (KRITISCH - HÖCHSTE PRIORITÄT!):
- Die ersten 2 SEKUNDEN = erste 8-12 Worte = ALLES!
- PFLICHT: Konkrete Zahl, Betrag oder Anzahl in den ersten 8-12 Worten!
- Hook-Qualität wichtiger als exakte Wortanzahl (72 vs 75-85 Worte ist ok bei perfektem Hook)

🔥 HOOK-FORMELN (mindestens eine nutzen):
1. **Konkrete Summe + Versprechen**: "[Betrag] geschenkt! So..."
2. **Warnung + Konkreter Verlust**: "Achtung: Dieser Fehler kostet [Betrag]!"
3. **Anzahl Betroffene + Relevanz**: "[Millionen] Menschen betroffen!"
4. **Zeitdruck + Vorteil**: "Nur noch bis [Datum]: [Betrag] sichern!"
5. **Schock-Element**: "Krass: Hier verschenken Deutsche [Betrag]!"

✅ PERFEKTE HOOK-BEISPIELE (alle mit Zahlen in ersten 8-12 Worten):
  * "1.076 Euro geschenkt! So nutzen Sie den Renten-Freibetrag!"
  * "Achtung: Dieser Fehler kostet Rentner 430 Euro monatlich!"
  * "21 Millionen Rentner betroffen – das ändert sich jetzt!"
  * "Krass: Hier verschenken Verbraucher 500 Euro pro Jahr!"
  * "Nur noch bis Dezember: So sichern Sie sich 800 Euro!"
  * "2.400 Euro Verlust! Dieser Renten-Fehler ist fatal!"

❌ SCHLECHTE HOOKS (NIEMALS SO):
  * "Vorsicht bei der Rente – das wird teuer!" → KEINE Zahl!
  * "Krass: So viel Geld verschenken die meisten!" → Zahl zu spät!
  * "Das sollten alle Rentner wissen..." → Langweilig, keine Zahl!

📊 STRUKTUR (Promipool TikTok Playbook):
1. **HOOK** (0-2 Sek., erste 8-12 Worte): Schockierender Fakt, überraschende Zahl, dringende Warnung
2. **MAIN STORY** (2-85 Sek.):
   - Kerninfos und wichtigste Fakten
   - Details, Hintergrund und Zusammenhänge
   - Konkrete Beispiele oder Zahlen
   - Bedeutung und praktische Konsequenzen
3. **OUTRO** (85-100 Sek.): Handlungsaufforderung, Ausblick oder wichtigster Takeaway

🎨 TONALITÄT (Lifestyle/Verbraucher):
- Informativ, seriös, leicht emotional
- Klare, verständliche Sprache (KEINE Slang-Begriffe)
- Sachlich aber zugänglich
- Fokus auf praktischen Nutzen: "Das bedeutet für Verbraucher", "Darauf sollten Sie achten"
- **🚨 KRITISCH: Emotionale Füllwörter EXTREM sparsam einsetzen!**
  * "Doch aufgepasst!", "Und das Beste?", "Aber Vorsicht!" → MAXIMAL 1x pro Script!
  * Bei langem Script (1:30 Min.): maximal 2x erlaubt
  * Mehr als 2x wirkt unseriös und übertrieben!
  * Übertreibungen vermeiden - Fakten sprechen für sich
  * Balance zwischen lebendig und seriös halten

  ❌ BEISPIEL FALSCH (zu viele Füllwörter):
  "1.076 Euro! Und das Beste? Pro Kind 228 Euro! Doch aufgepasst! Überschreitung = 40%..."
  → 3x Füllwörter in kurzem Script = UNSERIÖS!

  ✅ BEISPIEL RICHTIG (sparsam):
  "1.076 Euro Freibetrag! Pro Kind 228 Euro extra. Überschreitung wird zu 40% angerechnet..."
  → 0-1x Füllwörter = SERIÖS!, "Das können Betroffene tun"

#️⃣ HASHTAGS (am Ende):
Füge 3-5 relevante Hashtags hinzu, z.B.:
- Für Wirtschafts-Themen: #wirtschaft #industrie #unternehmen #standort #konjunktur
- Für Renten-Themen: #rente #altersvorsorge #finanzen #verbraucher #geldtipps
- Für Verbraucher-Themen: #verbraucher #verbraucherschutz #spartipps #finanztipps #geldsparen
- Für Gesundheit: #gesundheit #krankenkasse #verbraucher #gesundheitstipps
- Für Wohnen: #miete #wohnen #mietrecht #immobilien #verbraucher

⚡ WICHTIG:
- Exakt 150-180 Worte (zähle genau!)
- KEINE Anrede, KEINE Verabschiedung
- Fließtext ohne Überschriften
- Zum Sprechen geeignet
- Der Hook ist das Wichtigste! Erste 2 Sekunden = erste 8-12 Worte!
- Baue mehrere Informationsebenen ein
- Nutze konkrete Details aus dem Artikel

BEISPIEL mit starkem Hook (165 Worte):
"Ab Januar: So holen sich 21 Millionen Rentner bis zu 70 Euro mehr! Die Bundesregierung hat eine Rentenreform beschlossen, die jeden betrifft. Die wichtigste Änderung: Die Rente steigt um 3,5 Prozent. Das bedeutet konkret: Wer aktuell 1.500 Euro Rente bekommt, erhält künftig 52,50 Euro mehr pro Monat. Bei 2.000 Euro Rente sind es sogar 70 Euro zusätzlich. Die Auszahlung erfolgt automatisch, Rentner müssen nichts beantragen. Doch es gibt noch mehr Neuerungen. Die Hinzuverdienstgrenze wird komplett aufgehoben. Rentner können künftig unbegrenzt dazuverdienen, ohne dass ihre Rente gekürzt wird. Das ist besonders interessant für alle, die im Ruhestand weiterarbeiten möchten. Experten rechnen damit, dass die Erhöhung die gestiegenen Lebenshaltungskosten teilweise ausgleicht. Allerdings warnt die Verbraucherzentrale: Bei steigenden Energiepreisen und Inflation könnte die Erhöhung schnell aufgebraucht sein. Rentner sollten daher ihre Ausgaben im Blick behalten und gegebenenfalls zusätzliche Unterstützung beantragen. #rente #rentenerhöhung #altersvorsorge #finanzen #verbraucher"

Artikel:
{result_text}

Erstelle jetzt das ausführliche TikTok-Script mit starkem Hook (150-180 Worte + Hashtags):"""

    return generate_text(prompt)

def get_jina_content(url):
    full_url = f"https://r.jina.ai/{url}"
    response = requests.get(full_url)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch content from Jina.ai: {response.status_code}")

def process_multiple_urls(urls):
    combined_text = ""
    url_contents = {}
    for url in urls:
        try:
            article = Article(url.strip())
            article.download()
            article.parse()
            url_contents[url] = article.text
            combined_text += article.text + "\n\n"
            st.success(f"Successfully processed: {url}")
        except Exception as e:
            st.warning(f"Failed to process URL with newspaper3k: {e}. Trying Jina.ai...")
            try:
                content = get_jina_content(url.strip())
                url_contents[url] = content
                combined_text += content + "\n\n"
                st.success(f"Successfully processed with Jina.ai: {url}")
            except Exception as jina_error:
                st.error(f"An error occurred while processing the URL {url}: {jina_error}")
    return combined_text, url_contents

def main():
    col1, col2, col3 = st.columns(3)

    with col1:
        st.title("Generate Lifestyle/Verbraucher Article")

        st.subheader("Input URLs")
        num_url_inputs = st.number_input("Number of URLs to process", min_value=0, max_value=5, value=1)
        urls = []
        for i in range(num_url_inputs):
            url = st.text_input(f"Enter URL {i+1}", key=f"url_{i}")
            if url:
                urls.append(url)

        user_text = st.text_area("Or enter the text you'd like to rewrite:", height=200)
        custom_instructions = st.text_area(
            "Custom Instructions (Optional)",
            help="Add specific instructions for tone, style, focus areas, or any other special requirements.",
            placeholder="Example: 'Focus more on practical tips' or 'Emphasize legal aspects'",
            height=150
        )

        uploaded_file = st.file_uploader("Or upload a PDF file:", type="pdf")

        st.warning("If URL scraping doesn't work, we'll try using Jina.ai as a fallback.", icon="⚠️")

        if st.button("Generate Article from Sources"):
            result = original_text = None
            source = ""

            # Step 1: Process URLs
            if urls:
                with st.spinner(f'📥 Verarbeite {len(urls)} URL(s)...'):
                    original_text, url_contents = process_multiple_urls(urls)
                    source = ", ".join(urls)
                    st.success(f"✅ {len(urls)} URL(s) erfolgreich verarbeitet")

            # Step 2: Process user text
            if user_text.strip():
                if original_text:
                    original_text += "\n\n" + user_text.strip()
                    source += " and user provided text"
                else:
                    original_text = user_text.strip()
                    source = "User provided text"
                st.success("✅ Nutzer-Text hinzugefügt")

            # Step 3: Process PDF
            if uploaded_file is not None:
                with st.spinner('📄 Verarbeite PDF...'):
                    pdf_text = process_pdf(uploaded_file)
                    if original_text:
                        original_text += "\n\n" + pdf_text
                        source += " and uploaded PDF"
                    else:
                        original_text = pdf_text
                        source = "Uploaded PDF"
                    st.success("✅ PDF erfolgreich verarbeitet")

            # Step 4: Generate article
            if original_text:
                with st.spinner('🤖 Generiere SEO-optimierten Artikel... (ca. 30 Sek.)'):
                    source_info = create_source_info_lifestyle(urls, uploaded_file, bool(user_text.strip()), url_contents if 'url_contents' in locals() else {})
                    result = process_text_for_seo_enhanced_lifestyle(original_text, source_info, custom_instructions)
                    st.success("✅ Artikel generiert")

                # Step 5: Generate Video Articles (Lang & Kurz)
                with st.spinner('🎬 Generiere Video-Artikel (Lang & Kurz)... (ca. 40 Sek.)'):
                    video_article_long = process_text_for_video_article_long(result, source_info)
                    video_article_short = process_text_for_video_article_short(result, source_info)
                    st.success("✅ Video-Artikel generiert")

                # Display results in columns
                with col2:
                    st.title("Original Content:")
                    if 'url_contents' in locals():
                        for url, content in url_contents.items():
                            st.caption(f"Content from {url}")
                            st.write(content)
                            st.markdown("---")
                    if user_text.strip():
                        st.caption("User provided text")
                        st.write(user_text)
                    if uploaded_file is not None:
                        st.caption("Content from uploaded PDF")
                        st.write(pdf_text[:1000] + "..." if len(pdf_text) > 1000 else pdf_text)

                with col3:
                    if original_text:
                        title, subtitle, abstract, content, meta = extract_article_components(result)
                        st.session_state['title'] = title
                        st.session_state['subtitle'] = subtitle
                        st.session_state['abstract'] = abstract
                        st.session_state['content'] = content
                        st.session_state['meta'] = meta

                        article_container = display_article()

                        # Display Video Articles
                        st.markdown("---")
                        st.subheader("📹 Video-Artikel Formate")

                        with st.expander("🎬 Video-Artikel Lang (150-180 Wörter, mit Meta & Hashtags)", expanded=True):
                            video_headline_long, video_content_long, video_meta_long = extract_video_article_components(video_article_long)
                            st.markdown(f"""### {video_headline_long}

{video_content_long}

**Metabeschreibung:** {video_meta_long}""")
                            st.caption(f"📊 Wortanzahl: {len(video_content_long.split())} Worte")

                            # Speichere Video-Artikel Lang in Session State
                            st.session_state['video_article_long_headline'] = video_headline_long
                            st.session_state['video_article_long_content'] = video_content_long
                            st.session_state['video_article_long_meta'] = video_meta_long

                        with st.expander("📝 Video-Artikel Kurz (120-150 Wörter, mit Meta & Hashtags)", expanded=False):
                            video_headline_short, video_content_short, video_meta_short = extract_video_article_components(video_article_short)
                            st.markdown(f"""### {video_headline_short}

{video_content_short}

**Metabeschreibung:** {video_meta_short}""")
                            st.caption(f"📊 Wortanzahl: {len(video_content_short.split())} Worte")

                            # Speichere Video-Artikel Kurz in Session State
                            st.session_state['video_article_short_headline'] = video_headline_short
                            st.session_state['video_article_short_content'] = video_content_short
                            st.session_state['video_article_short_meta'] = video_meta_short

                        send_article_to_pp_fragment()
                        edit_article(article_container)

                # Update Google Sheet
                current_date = time.strftime("%Y-%m-%d")
                current_time = time.strftime("%H:%M:%S")
                success, message = update_google_sheet(
                    current_date,
                    current_time,
                    source,
                    original_text,
                    result,
                    video_article_long,
                    video_article_short,
                    "Lifestyle-Verbraucher-Tool"
                )

                if not success:
                    st.warning(f"Warning: {message}")
                elif "truncated" in message.lower():
                    st.info(message)

            else:
                st.error("No content to process. Please provide URLs, enter text, or upload a PDF file.")

if __name__ == "__main__":
    main()
