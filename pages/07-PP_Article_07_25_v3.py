from openai import OpenAI
import time
from rich import print
import requests
import pandas as pd 
import streamlit as st
from newspaper import Article
import gspread
#from oauth2client.service_account import ServiceAccountCredentials
import json
import re
import PyPDF2
import io

# Page configuration 
st.set_page_config(
    page_title="Generate SEO Article from Multiple URLs or Text",
    page_icon="☎",
    layout="wide"
)

# Define the API key and server URL
API_KEY = "TfrBdFP-dEYYXdL4stRuG8frztLhRf_sEMfuZkPrhi2-Fpq2R"
SERVER_URL = "https://p1.promipool.de/api/articles"
PP_API_KEY = "7cd84bed39a44cdd53c256431aa47c55f284985b"
PP_SERVER_URL ="https://www.promipool.de/api/content-drafts/create"# "https://stage.promipool.de/api/content-drafts/create"

# Setup the gspread authentication using the details from Streamlit secrets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

#credentials = ServiceAccountCredentials.from_json_keyfile_dict({
#    "type": "service_account",
#    "project_id": st.secrets["gs-project_id"],
#    "private_key_id": st.secrets["gs-private_key_id"],
#    "private_key": st.secrets["gs-private_key"],
#    "client_email": st.secrets["gs-client_email"],
#    "client_id": st.secrets["gs-client_id"],
#    "auth_uri": st.secrets["gs-auth_uri"],
#    "token_uri": st.secrets["gs-token_uri"],
#    "auth_provider_x509_cert_url": st.secrets["gs-auth_provider_x509_cert_url"],
#    "client_x509_cert_url": st.secrets["gs-client_x509_cert_url"]
#}, scope)

#client = gspread.authorize(credentials)

# Initialize the Google Sheet and worksheet
# spreadsheet = client.open("Promipool_AI_Logs")  # Replace with your actual sheet name
# worksheet = spreadsheet.worksheet("News")  # Replace with your actual worksheet name

# Streamlit UI layout
col1, col2, col3 = st.columns(3)

def create_source_info_promipool(urls, uploaded_file=None, user_text_provided=False, url_contents=None):
    """
    Erstellt erweiterte Quelleninfo für bessere Zitierung im Promipool Artikel.
    """
    from urllib.parse import urlparse
    
    def extract_domain_info(url):
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            
            # ERWEITERTE Entertainment-Quellen-Mapping
            entertainment_source_mapping = {
                # Boulevard & Celebrity News
                'bild.de': ('Bild', 'Boulevard-Zeitung Bild', 'Celebrity-News und Prominenten-Skandale'),
                'express.de': ('Express', 'Boulevard-Zeitung Express', 'Prominenten-News und Entertainment'),
                'mopo.de': ('Hamburger Morgenpost', 'Morgenpost', 'lokale Celebrity-News'),
                
                # TV & Entertainment
                'rtl.de': ('RTL', 'TV-Sender RTL', 'Reality-TV und Entertainment-Shows'),
                'prosieben.de': ('ProSieben', 'TV-Sender ProSieben', 'Entertainment und Show-Business'),
                'sat1.de': ('Sat.1', 'TV-Sender Sat.1', 'Entertainment und Reality-Formate'),
                'vox.de': ('VOX', 'TV-Sender VOX', 'Lifestyle-Shows und Entertainment'),
                'rtl2.de': ('RTL2', 'TV-Sender RTL2', 'Reality-TV und Jugend-Entertainment'),
                
                # Celebrity & Lifestyle Magazine
                'gala.de': ('Gala', 'Lifestyle-Magazin Gala', 'Celebrity-Lifestyle und Society-News'),
                'bunte.de': ('Bunte', 'People-Magazin Bunte', 'Prominenten-Stories und Adel-News'),
                'ok-magazin.de': ('OK! Magazin', 'Celebrity-Magazin OK!', 'Prominenten-Klatsch'),
                'intouch.de': ('InTouch', 'Lifestyle-Magazin InTouch', 'Celebrity-Trends und Beauty'),
                'closer.de': ('Closer', 'People-Magazin Closer', 'Prominenten-Geheimnisse'),
                'frau-im-spiegel.de': ('Frau im Spiegel', 'Frauenmagazin', 'Celebrity-Lifestyle'),
                'neue-post.de': ('Neue Post', 'Boulevardmagazin Neue Post', 'Prominenten-News'),
                
                # Online Entertainment Portals
                'promiflash.de': ('Promiflash', 'Celebrity-Portal Promiflash', 'aktuelle Prominenten-News'),
                'spot-on-news.de': ('Spot On News', 'Entertainment-Portal', 'Celebrity-News'),
                'schlager.de': ('Schlager.de', 'Musik-Portal', 'Schlager-Stars und Musik'),
                
                # Social Media & Influencer
                'instagram.com': ('Instagram', 'Social Media Plattform Instagram', 'Influencer-Content'),
                'tiktok.com': ('TikTok', 'Social Media Plattform TikTok', 'Viral-Content'),
                'youtube.com': ('YouTube', 'Video-Plattform YouTube', 'Creator-Content'),
                'facebook.com': ('Facebook', 'Social Media Plattform Facebook', 'Celebrity-Updates'),
                
                # News Portals (Entertainment sections)
                'spiegel.de': ('Spiegel', 'Nachrichtenmagazin Spiegel', 'Celebrity-News und Kultur'),
                'focus.de': ('Focus', 'Nachrichtenmagazin Focus', 'Prominenten-News'),
                'stern.de': ('Stern', 'Nachrichtenmagazin Stern', 'Celebrity-Stories'),
                'welt.de': ('Welt', 'Tageszeitung Die Welt', 'Celebrity-News und Kultur'),
                't-online.de': ('t-online.de,', 'Online-Portal t-online.de', 'Entertainment-News'),

                
                # Streaming & Entertainment
                'netflix.com': ('Netflix', 'Streaming-Dienst Netflix', 'Serie-Stars und Content'),
                'amazon.de': ('Amazon Prime', 'Streaming-Dienst Amazon Prime', 'Serie-News'),
                'disney.de': ('Disney+', 'Streaming-Dienst Disney+', 'Disney-Stars'),
                
                # International Entertainment
                'tmz.com': ('TMZ', 'US-Entertainment-Portal TMZ', 'internationale Celebrity-News'),
                'people.com': ('People Magazine', 'US-Magazin People', 'internationale Star-News'),
                'dailymail.co.uk': ('Daily Mail', 'britische Zeitung Daily Mail', 'internationale Promis')
            }
            
            for key, (name, description, content_focus) in entertainment_source_mapping.items():
                if key in domain.lower():
                    return domain, name, description, content_focus
            
            return domain, domain, f"Entertainment-Quelle {domain}", "Entertainment-Informationen"
            
        except Exception:
            return url, url, f"Online-Quelle {url}", "allgemeine Informationen"
    
    # Rest der Funktion bleibt gleich...
    if not url_contents:
        url_contents = {}
    
    source_info = "QUELLENVERZEICHNIS FÜR PROMIPOOL ARTIKEL:\n"
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

def analyze_theme_module_promipool_original(article_text: str, source_info: str = "") -> str:
    """
    Erkennt die Promipool-Kategorie automatisch - KORRIGIERT
    """
    full_text = (article_text + " " + source_info).lower()
    
    modules = {
        'ROYALS': {  # ← ROYALS ZUERST prüfen!
            'keywords': ['royal', 'royals', 'königin elisabeth', 'könig charles', 'prinz william', 'herzogin kate', 'prinz harry', 'herzogin meghan', 'königshaus', 'adel', 'krone', 'thron', 'majestät', 'buckingham palace', 'clarence house'],
            'high_priority': ['royal', 'royals', 'königin elisabeth', 'könig charles', 'prinz william', 'prinz harry', 'königshaus']  # ← Mehr High-Priority
        },
        'STARS': {
            'keywords': ['star', 'stars', 'promi', 'promis', 'celebrity', 'vip', 'helene fischer', 'andrea berg', 'geissens', 'wollnys', 'influencer', 'skandal'],
            'high_priority': ['star', 'promi', 'celebrity', 'helene fischer', 'geissens']
        },
        'TV_FILM': {
            'keywords': ['tv', 'serie', 'film', 'bares für rares', 'sturm der liebe', 'netflix', 'streaming', 'sendung', 'show'],
            'high_priority': ['tv', 'serie', 'film', 'netflix', 'bares für rares']
        },
        'RETRO': {
            'keywords': ['retro', 'was wurde aus', 'patrick swayze', 'elvis presley', 'unsere kleine farm', 'dirty dancing', 'kult'],
            'high_priority': ['retro', 'was wurde aus', 'patrick swayze', 'elvis presley']
        },
        'SCHLAGER': {
            'keywords': ['schlager', 'helene fischer', 'florian silbereisen', 'beatrice egli', 'andrea berg', 'vanessa mai', 'konzert'],
            'high_priority': ['schlager', 'helene fischer', 'florian silbereisen', 'beatrice egli']
        },
        'STYLE': {
            'keywords': ['style', 'fashion', 'beauty', 'red carpet', 'outfit', 'look', 'heidi klum', 'stefanie giesinger'],
            'high_priority': ['style', 'fashion', 'beauty', 'red carpet', 'heidi klum']
        }
    }
    
    scores = {}
    for module_name, module_data in modules.items():
        score = 0
        for keyword in module_data['keywords']:
            score += full_text.count(keyword)
        for priority_keyword in module_data['high_priority']:
            score += full_text.count(priority_keyword) * 5  # ← Erhöht von 3 auf 5!
        scores[module_name] = score
    
    if max(scores.values()) == 0:
        return 'STARS'
    
    primary_module = max(scores, key=scores.get)

    return primary_module

def get_module_info_promipool_original(module_key: str) -> dict:
    """
    Gibt Informationen zur erkannten Kategorie zurück
    """
    modules_info = {
        'STARS': {
            'name': 'Stars',
            'focus': 'Aktuelle Prominenten-Nachrichten und Star-Updates',
            'hashtags': ['#Celebrity', '#Promi', '#Star', '#VIP', '#Entertainment']
        },
        'TV_FILM': {
            'name': 'TV & Film',
            'focus': 'TV, Film und Streaming Entertainment',
            'hashtags': ['#TV', '#Film', '#Serie', '#Netflix', '#Streaming']
        },
        'ROYALS': {
            'name': 'Royals',
            'focus': 'Königshäuser und Adel weltweit',
            'hashtags': ['#Royals', '#Königshaus', '#Adel', '#KöniginElisabeth', '#PrinzWilliam']
        },
        'RETRO': {
            'name': 'Retro',
            'focus': 'Retro-Entertainment und Kult-Stars',
            'hashtags': ['#Retro', '#Kult', '#Nostalgie', '#WasWurdeAus', '#PatrickSwayze']
        },
        'SCHLAGER': {
            'name': 'Schlager',
            'focus': 'Schlager-Musik und Entertainment-Shows',
            'hashtags': ['#Schlager', '#HeleneFischer', '#Konzert', '#Charts', '#Musik']
        },
        'STYLE': {
            'name': 'Style',
            'focus': 'Fashion und Lifestyle von Prominenten',
            'hashtags': ['#Fashion', '#Style', '#Beauty', '#RedCarpet', '#CelebrityStyle']
        }
    }
    
    return modules_info.get(module_key, modules_info['STARS'])

def extract_real_quotes_from_source_promipool(text):
    """
    ZURÜCK ZU DIREKTEN ZITATEN - wie BPM, aber für Promipool angepasst
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
            # Filtere störende Inhalte
            if not any(x in match for x in [
                '|', ':', 'Breaking', 'News', 'Copyright', 'Anzeige', 'Image', 
                'Learn More', 'Akzeptieren', 'Cookie', 'Datenschutz', 'Impressum',
                'Menü', 'Ressorts', 'Untermenü', 'Newsletter', 'Abo', 'Login',
                'EPA', 'dpa', 'Quelle', 'zu sehen hier', 'Peter Dejong',
                # NEUE FILTER für Entertainment-Display-Texte:
                'Mein Ex', 'Papa', 'Mama', 'Anruf von', 'Kontakt', 'Telefon',
                'App', 'Nachricht', 'SMS', 'WhatsApp', 'Instagram', 'Facebook',
                'Display', 'Handy', 'Smartphone', 'Benachrichtigung'
            ]):
                # FOKUS: Nur DIREKTE ZITATE von Personen
                if any(term in match.lower() for term in [
                    # Direkte Ich-Form (wie BPM)
                    'ich', 'mein', 'mir', 'bin', 'habe', 'will', 'kann', 'möchte',
                    'liebe', 'freue', 'denke', 'glaube', 'finde', 'sage', 'würde',
                    
                    # Direkte Wir-Form (Promipool: Paare/Familien)
                    'wir', 'uns', 'unser', 'unsere', 'werden', 'sind'
                ]):
                    # Mindestens 20 Zeichen für substantielle Zitate
                    if len(match) > 20:
                        quotes.append(match.strip())
    
    # Duplikate entfernen und sortieren
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

def extract_sources_from_info_promipool(source_info):
    """
    Extrahiert Quellennamen für Zitierung
    """
    import re
    sources = []
    
    pattern = r'Quelle\s+\d+:\s+([^(]+)\s*\(([^)]+)\)'
    matches = re.findall(pattern, source_info)
    
    for description, domain in matches:
        if 'bild' in description.lower():
            sources.append('Bild')
        elif 'rtl' in description.lower():
            sources.append('RTL')
        elif 'gala' in description.lower():
            sources.append('Gala')
        elif 'bunte' in description.lower():
            sources.append('Bunte')
        else:
            clean_domain = domain.replace('www.', '').replace('.de', '').replace('.com', '')
            sources.append(clean_domain.capitalize())
    
    return sources

def extract_concrete_facts_promipool(text):
    """
    Extrahiert konkrete Entertainment-Fakten und Zahlen aus dem Quellentext
    """
    import re
    facts = []
    
    # Entertainment-spezifische Fakten Patterns
    patterns = [
        # Follower, Views, Likes etc.
        r'\d+(?:\.\d+)?\s*(?:Follower|Likes|Views|Abonnenten|Fans|Zuschauer)',
        r'\d+(?:\.\d+)?\s*(?:Millionen|Mio\.|Milliarden|Mrd\.)\s*(?:Follower|Likes|Views|Fans)',
        
        # Sendungsquoten und TV-Daten
        r'\d+(?:,\d+)?\s*(?:Prozent|%)\s*(?:Marktanteil|Quote|Einschaltquote)',
        r'\d+(?:\.\d+)?\s*(?:Millionen|Mio\.)\s*(?:Zuschauer|Seher)',
        
        # Alter, Beziehungsdaten
        r'(?:ist|war|wurde)\s+\d{1,2}\s*(?:Jahre|Jahr)\s*(?:alt|jung)',
        r'seit\s+\d{1,4}\s*(?:verheiratet|zusammen|verlobt|getrennt)',
        
        # Geld und Einnahmen (Entertainment relevant)
        r'\d+(?:\.\d+)?\s*(?:Euro|€|Dollar|\$|Millionen|Milliarden)\s*(?:Gage|Honorar|Einkommen|Vermögen)',
        
        # Jahreszahlen (Entertainment-Kontext)
        r'(?:seit|vor|nach|in)\s+\d{4}',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) > 3:  # Nur relevante Fakten
                facts.append(match.strip())
    
    # Entferne Duplikate und sortiere nach Länge
    facts = list(set(facts))
    facts.sort(key=len, reverse=True)
    
    return facts[:10]  # Max 10 konkrete Entertainment-Fakten

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

# =============================================================================
# ENDE DER NEUEN FUNKTIONEN
# =============================================================================

def truncate_text_for_sheets(text: str, max_length: int = 45000) -> str:
    """
    Truncates text to ensure it fits within Google Sheets cell limits.
    Adds indicator if text was truncated. 
    
    Args:
        text: The text to truncate
        max_length: Maximum allowed length (default: 49000 to leave safety margin)
        
    Returns:
        str: Truncated text with indicator if needed
    """
    if not text:
        return ""
        
    if len(text) <= max_length:
        return text
        
    truncated_text = text[:max_length]
    truncation_indicator = "... [TEXT TRUNCATED DUE TO LENGTH]"
    
    # Ensure we have room for the indicator
    final_text = truncated_text[:max_length - len(truncation_indicator)] + truncation_indicator
    return final_text

def update_google_sheet(date: str, time: str, source: str, original_text: str, 
                    result_text: str, tool: str) -> tuple[bool, str]:
    """
    Updates Google Sheet with article generation data, handling potential errors.
    
    Args:
        date: Current date
        time: Current time
        source: Source of the content (URLs or text input)
        original_text: Original input text
        result_text: Generated article text
        tool: Tool identifier
        
    Returns:
        tuple[bool, str]: (success status, message)
    """
    try:
        # Truncate long text fields
        truncated_source = truncate_text_for_sheets(source)
        truncated_original = truncate_text_for_sheets(original_text)
        truncated_result = truncate_text_for_sheets(result_text)
        
        # Attempt to append row
        worksheet.append_row([
            date,
            time,
            truncated_source,
            truncated_original,
            truncated_result,
            tool
        ])
        
        # Check if any truncation occurred
        was_truncated = (len(source) > 49000 or 
                        len(original_text) > 49000 or 
                        len(result_text) > 49000)
        
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

#new OpenAi Client, old model: gpt-4o, gpt-4o-2024-08-06, gpt-4o-mini
def generate_text(prompt, model="gpt-4o-2024-08-06", temperature=0.5, max_retries=3):
    client = OpenAI(api_key=st.secrets["openai"], max_retries=max_retries)
    messages = [{"role": "user", "content": prompt}]
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def remove_markdown(text):
    """
    Erweiterte Funktion zum Entfernen von Markdown-Formatierung, einschließlich Überschriften.
    """
    # Entferne Markdown-URLs
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1', text)
    # Entferne Markdown-Überschriften
    text = re.sub(r'^\#{1,6}\s*(.+)', r'\1', text, flags=re.MULTILINE)
    # Entferne einfache Markdown-Formatierungen wie **bold**, *italic*, etc.
    text = re.sub(r'\*{1,2}([^\*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'\_{1,2}([^\_]+)\_{1,2}', r'\1', text)
    # Entferne Code-Zeichen
    text = text.replace('`', '')
    # Entferne Blockquotes
    text = text.replace('> ', '')
    return text

@st.experimental_fragment
def send_article_to_pp_fragment():
    if 'title' not in st.session_state or 'subtitle' not in st.session_state or 'content' not in st.session_state or 'meta' not in st.session_state:
        st.warning("Please generate an article first before sending to API.")
        return

    if st.button("Send Article to API"):
        title = st.session_state.get('title', '').strip()
        subtitle = st.session_state.get('subtitle', '').strip()
        abstract = st.session_state.get('abstract', '').strip()
        content = st.session_state.get('content', '').strip()
        meta = st.session_state.get('meta', '').strip()

        if not title or not subtitle:
            st.error("Title and subtitle are required. Please ensure both are generated.")
            return

        api_response = send_article_to_pp(title, subtitle, abstract, content, meta)
        
        if 'error' not in api_response:
            st.success("Der Artikel wurde erfolgreich an Promipool API gesendet.")
        else:
            st.error(f"Fehler beim Senden des Artikels: {api_response['error']}")
            # Only show response details on error
            with st.expander("API Response Details"):
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
                "response": response.json() if response.text else {}
            }
        else:
            return {
                "success": False,
                "error": f"Unexpected status code: {response.status_code}",
                "response_text": response.text
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
        
@st.experimental_fragment
def test_content_formatting_fragment():
    """
    Streamlit fragment for testing content formatting.
    Shows both display format (###) and API format (#).
    """
    if 'content' not in st.session_state:
        st.warning("Please generate an article first before testing.")
        return

    if st.button("Test Content Formatting"):
        content = st.session_state.get('content', '').strip()
        
        with st.expander("Content Formatting Test Results", expanded=True):
            st.write("=== Display Content (with ###) ===")
            st.code(content, language="markdown")
            
            st.write("\n=== API Content (with #) ===")
            api_content = format_content_for_api(content)
            st.code(api_content, language="markdown")
                    

def clean_article_text(text: str, is_intro: bool = False) -> str:
    """
    Clean article text while preserving markdown structure.
    Better handling of bold text vs headers.
    
    Args:
        text (str): The input text containing markdown formatting
        is_intro (bool): Flag to indicate if this is intro/abstract text
        
    Returns:
        str: Cleaned text with preserved structure but no markdown
    """
    if not text:
        return ""

    # Remove quotes from intro if needed
    if is_intro:
        text = text.strip('"')
    
    # Split text into paragraphs first
    paragraphs = text.split('\n\n')
    cleaned_paragraphs = []
    
    for paragraph in paragraphs:
        # Skip empty paragraphs
        if not paragraph.strip():
            continue
            
        lines = paragraph.strip().split('\n')
        cleaned_lines = []
        
        for line in lines:
            clean_line = line.strip()
            
            # Skip empty lines
            if not clean_line:
                continue
                
            # Handle markdown headers (##)
            if clean_line.startswith('##'):
                clean_line = clean_line.replace('##', '').strip()
                cleaned_lines.append(clean_line)
                continue
                
            # Handle bold text (enclosed in **)
            if clean_line.startswith('**') and clean_line.endswith('**'):
                clean_line = clean_line[2:-2].strip()  # Remove asterisks
            
            # Remove any remaining asterisks
            clean_line = clean_line.replace('*', '')
            
            # Skip Artikeltext: marker
            if clean_line.startswith('Artikeltext:'):
                continue
                
            cleaned_lines.append(clean_line)
        
        if cleaned_lines:
            cleaned_paragraphs.append('\n'.join(cleaned_lines))
    
    # Join paragraphs with double newlines
    return '\n\n'.join(cleaned_paragraphs)

def extract_article_components(article_result: str) -> tuple:
    """
    Extract components from GPT's output, keeping markdown intact.
    Extracts but ignores keywords section to keep meta description clean.
    """
    # Define patterns that match the sections
    title_pattern = r"Titel:\s*(.*?)\n+"
    subtitle_pattern = r"Untertitel:\s*(.*?)\n{2,}"
    abstract_pattern = r"Abstract:\s*(.*?)\n{2,}"
    meta_pattern = r"Metabeschreibung:\s*(.*?)(?:\nKeywords:|$)"  # Stop at Keywords or end of string

    # Extract components
    title = re.search(title_pattern, article_result, re.DOTALL)
    subtitle = re.search(subtitle_pattern, article_result, re.DOTALL)
    abstract = re.search(abstract_pattern, article_result, re.DOTALL)
    meta = re.search(meta_pattern, article_result, re.DOTALL)

    # Get content by removing other components
    content = article_result
    if title:
        content = re.sub(title_pattern, "", content, flags=re.DOTALL).strip()
    if subtitle:
        content = re.sub(subtitle_pattern, "", content, flags=re.DOTALL).strip()
    if abstract:
        content = re.sub(abstract_pattern, "", content, flags=re.DOTALL).strip()
    if meta:
        # Remove both meta and keywords section together
        content = re.sub(r"Metabeschreibung:.*?(?:\nKeywords:.*?)?$", "", content, flags=re.DOTALL).strip()

    # Clean up components
    clean_title = title.group(1).replace('\n', ' ').strip() if title else ""
    clean_subtitle = subtitle.group(1).replace('\n', ' ').strip() if subtitle else ""
    clean_abstract = abstract.group(1).replace('\n', ' ').strip() if abstract else ""
    clean_content = re.sub(r"Artikeltext:\s*\n+", "", content, flags=re.MULTILINE).strip()
    clean_meta = meta.group(1).strip() if meta else ""
    
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
    # Container für den Artikel erstellen
    article_display = st.empty()
    
    # Wir lesen den update_counter, auch wenn wir ihn nicht direkt nutzen
    # Das zwingt Streamlit dazu, das Fragment neu zu rendern wenn sich der Counter ändert
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
                
                # Extrahiere die Komponenten aus dem überarbeiteten Artikel
                title, subtitle, abstract, content, meta = extract_article_components(enhanced_article)
                
                # Aktualisiere den Session State
                st.session_state.title = title
                st.session_state.subtitle = subtitle
                st.session_state.abstract = abstract
                st.session_state.content = content
                st.session_state.meta = meta
                
                # Direkt den Container aktualisieren
                article_display.markdown(f"""# Generated Article Content:

Titel: {st.session_state.title}

Untertitel: {st.session_state.subtitle}

Abstract: {st.session_state.abstract}

Artikeltext:
{st.session_state.content}

Metabeschreibung: {st.session_state.meta}
""")
                
                st.success("Artikel wurde erfolgreich überarbeitet!")
                
def process_text_for_seo_enhanced_promipool(article_text: str, source_info: str = "", custom_instructions: str = "") -> str:
    """
    Erweiterte SEO-Funktion mit ALLEN BP-Features + Original Promipool-Struktur
    """
    # SCHRITT 1: Automatische Promipool-Kategorie-Erkennung (wie BPM)
    primary_module = analyze_theme_module_promipool_original(article_text, source_info)
    module_info = get_module_info_promipool_original(primary_module)
    
    print(f"🎯 Erkannte Promipool-Kategorie: {module_info['name']} ({primary_module})")
    print(f"📊 Fokus: {module_info['focus']}")
    
    # SCHRITT 2: Extrahiere echte Zitate und Fakten (wie BPM)
    real_quotes = extract_real_quotes_from_source_promipool(article_text)
    concrete_facts = extract_concrete_facts_promipool(article_text)  # ← DAS FEHLTE!
    available_sources = extract_sources_from_info_promipool(source_info)
    
    # SCHRITT 3: Erstelle erweiterten Prompt (wie BPM)
    base_prompt = f"""KRITISCHE ANTI-HALLUZINATIONS-REGELN FÜR PROMIPOOL - STRIKT BEFOLGEN:

1. QUELLEN UND ZITATE (Entertainment-fokussiert):
    - Verfügbare Entertainment-Quellen: {', '.join(available_sources) if available_sources else 'Nutze die Quellen aus der Quellenliste'}

   WICHTIG FÜR PROMIPOOL-QUELLENANGABEN:
    - ALLE Quellennamen im Text IMMER kursiv: *Bild.de*, *RTL.de*, *Gala.de*, *Bunte.de*, *ProSieben.de*
    - IMMER kursiv hervorgehoben: laut *RTL.de*
    - FORMAT: laut *Quelle*, *Quelle* berichtet, wie *Quelle* meldet
    - BEISPIELE: laut *Bild.de*, so *Gala.de*, wie *RTL.de* berichtet

   ZITATE (Celebrity/Entertainment-Fokus):
    - ABSOLUT KRITISCH: JEDES Celebrity-Zitat SOFORT mit Quelle
    - Format: „Zitat hier", so *Quellenname*
    - WORTGETREUE ÜBERNAHME: Celebrity-Zitate müssen EXAKT übernommen werden
    - DEUTSCHE ÜBERSETZUNG: Alle Zitate müssen ins Deutsche übersetzt werden

   FAKTEN-QUELLENANGABEN (1x pro Absatz):
    - EXTREM WICHTIG mindestens eine strategische Quellenangabe pro Absatz
    - WANN: Bei wichtigen Celebrity-News, Show-Daten, kontroversen Aussagen
    - FORMAT: laut *Quellenname*, so *Quellenname* berichtet, wie *Quellenname* meldet

   ANFÜHRUNGSZEICHEN-VERBOT 
    - NIEMALS Anführungszeichen um Inhalte setzen, die im Original keine haben
    - Indirekte Rede bleibt OHNE Anführungszeichen  
    - NUR echte Celebrity-Direktzitate aus den Quellen in Anführungszeichen

2. ENTERTAINMENT-QUELLENVERTEILUNG:
    - Verfügbare Quellen: {', '.join(available_sources) if available_sources else 'Bild, RTL, Gala'}
    - ALLE Quellennamen immer kursiv: *Bild.de*, *RTL.de*, *Gala.de*
    - VARIATION PFLICHT - verwende unterschiedliche Formulierungen: laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | *Quelle* enthüllt
    - NIEMALS die gleiche Formulierung zweimal verwenden!
    - Balance: Wichtige Celebrity-Facts MIT Quelle, Allgemeinwissen OHNE Quelle

VERFÜGBARE ECHTE CELEBRITY-ZITATE AUS DEM ORIGINALTEXT:
{chr(10).join([f'• "{quote}" (direkte Aussage)' for quote in real_quotes[:5]]) if real_quotes else '• Keine direkten Celebrity-Zitate im Originaltext gefunden - verwende nur indirekte Rede'}

    WICHTIGE ZITAT-VERWENDUNGSREGELN (Entertainment):
    - Verwende die oben aufgelisteten echten DIREKTZITATE WÖRTLICH (keine Änderungen!)
    - NUR direkte Aussagen von Personen verwenden - keine Insider-Interpretationen
    - Jedes verwendete Zitat MUSS mit der korrekten Entertainment-Quelle versehen werden
    - Format: „Celebrity-Zitat hier", so *Quellenname*
    - Falls keine direkten Zitate verfügbar: NUR indirekte Rede im Konjunktiv I verwenden
    - NIEMALS eigene Celebrity-Zitate erfinden - nur die oben gelisteten verwenden!
    - ALLE Zitate müssen ins Deutsche übersetzt werden

    FOCUS: Direkte Aussagen von Prominenten > Insider-Spekulationen

    ZUSATZ BEI MEHRFACHQUELLEN:
    - Wenn ein Zitat in MEHREREN Quellen steht, schreibe: "so berichten mehrere Medien"
    - Bei unsicherer Quelle: "wie verschiedene Medien zitieren"

VERFÜGBARE ENTERTAINMENT-FAKTEN:
{chr(10).join([f'• {fact[:100]}...' for fact in concrete_facts[:5]]) if concrete_facts else '• Nutze nur Entertainment-Fakten aus dem bereitgestellten Originaltext'}

ERKANNTE PROMIPOOL-KATEGORIE: {primary_module} ({module_info['name']})
KATEGORIE-FOKUS: {module_info['focus']}

    PROMIPOOL-STIL OPTIMIERUNG (moderat emotional):
    - Nutze abwechslungsreiche Quellenangaben - NIEMALS dieselbe Formulierung zweimal:
    * laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | *Quelle* enthüllt
    - Verwende leicht emotionalere, aber respektvolle Sprache:
    * "zerrüttet" statt "angespannt" | "Knackpunkt" statt "Streitpunkt" | "Royal-Fans hoffen" statt "Insider hoffen"
    - Baue moderate Spannung auf: "Das könnte der Wendepunkt sein" | "Jetzt wird es spannend" | "Endlich Bewegung"
    - PROMIPOOL-SPRACHE: "Royal-Drama", "heimlich", "endlich", "überraschend", "bewegend"
    - Beginne Sätze dynamischer: "Endlich!", "Jetzt!", "Überraschung!", "Das wird spannend!"
    - Max. 2-3 Ausrufezeichen im ganzen Artikel für Betonung
    - WICHTIG: Seriös bleiben - keine Reißersprache oder Übertreibungen!

    PROMIPOOL ANTI-KI-STIL REGELN - STRIKT BEFOLGEN:
    - ABSOLUTES VERBOT: "Person, die bekannte...", "Person, bekannt aus..." 
    - NIEMALS: "Name, der/die [Beschreibung], hat..." Struktur verwenden
    - SOFORT STOPPEN bei Komma-Einschüben nach Personennamen
    - RICHTIG: "ARD-Moderatorin Name" oder einfach "Name" 
    - FALSCH-BEISPIEL: "Esther Sedlaczek, bekannt aus der ARD-Sportschau" 
    - RICHTIG-BEISPIEL: "ARD-Moderatorin Esther Sedlaczek" 

    PROMIPOOL ANTI-KI-FLOSKEL REGELN:
    - VERMEIDE Standard-KI-Phrasen wie:
    * "könnte der Wendepunkt sein" → "bringt alles ins Rollen"
    * "anheizt die Spekulationen" → "lässt die Gerüchteküche brodeln"  
    * "sorgten für Aufsehen" → "schlagen hohe Wellen"
    * "wollte sich nicht äußern" → "hüllt sich in Schweigen"
    * "obwohl es Hoffnungen gibt" → "trotz aller Hoffnung"

    PROMIPOOL-SPRACHE STATT KI-SPRACHE:
    - NICHT: "Das Treffen könnte wegweisend sein"
    - BESSER: "Jetzt wird es ernst zwischen Vater und Sohn"
    - NICHT: "Die Beziehung bleibt angespannt"  
    - BESSER: "Die royale Eiszeit dauert an"
    - NICHT: "weitere Besuche erschwert"
    - BESSER: "hält Harry fern von der Heimat"

    VERBOTENE SATZKONSTRUKTIONEN:
    - "[Name], bekannt aus [Show/Sender], hat..." 
    - "[Name], die/der beliebte [Beruf], hat..." 
    - "[Name], [Alter], ist..." 
    - IMMER direkt beginnen: "[Beruf] [Name]" oder "[Name]" 

    EMOTIONALE PROMIPOOL-WENDUNGEN:
    - "schlagen hohe Wellen", "brodelt die Gerüchteküche", "bringt Bewegung rein"
    - "jetzt wird es ernst", "die Eiszeit bröckelt", "royales Drama"
    - "lässt aufhorchen", "sorgt für Wirbel", "heizt Spekulationen an"

    PROMIPOOL-STIL VERSTÄRKEN:
    - Mehr direkte Sprache: "Harry will Frieden" statt "Harry äußerte den Wunsch"
    - Emotionalere Verben: "platzen", "brodeln", "explodieren", "durchsickern"
    - Royal-Drama Vokabular: "Palast-Insider", "royale Sensation", "Königshaus-Krach"
    - Persönlicher: "Der Prinz" statt "Prinz Harry" (gelegentlich abwechseln)
    - Spannung: "Was passiert wirklich?", "Bleibt alles beim Alten?"

    VERMEIDE DIESE KI-TRIGGER-WÖRTER:
    - "könnte", "möglicherweise", "allerdings", "jedoch", "dennoch" (zu häufig)
    - "offenbar", "berichten zufolge", "heißt es" (zu passiv)
    - "dies", "diese", "jene" (zu unpersönlich)
    - Meide KI-typische Wendungen: "dies führte zu", "dies sorgte für", "was zur Folge hatte"
    - "die bekannte", "der beliebte", "die erfolgreiche" (KI-Einschübe)
    - "frischgebackene", "stolze" (KI-Adjektive)  
    - "Dreifach-Mama", "Zweifach-Papa" (künstliche Wortkreationen)
    - Komma-Einschübe generell minimieren

    NATÜRLICHE DEUTSCHE ALTERNATIVEN:
    - STATT: "Esther Sedlaczek, die bekannte ARD-Moderatorin, hat..."
    - BESSER: "ARD-Moderatorin Esther Sedlaczek hat..." oder "Esther Sedlaczek hat..."
    - STATT: "Der frischgebackenen Dreifach-Mama geht es gut"  
    - BESSER: "Sedlaczek geht es gut" oder "Der Familie geht es gut"
    - STATT: "die beliebte Moderatorin"
    - BESSER: "Moderatorin" oder "Sedlaczek"

    QUELLENNUTZUNG MIT PROMIPOOL-FINGERSPITZENGEFÜHL:
    - Verfügbare Quellen: {', '.join([f'*{source}*' for source in available_sources])}
    - ZIEL: Alle Quellen verwenden, aber organisch und lesbar verteilt
    - BALANCE: Pro Absatz maximal 1-2 strategische Quellenangaben
    - VARIATION PFLICHT: Jede Quelle mit unterschiedlicher Formulierung:
    * laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | *Quelle* enthüllt
    - WANN zitieren: Bei wichtigen Facts, Enthüllungen, Zitaten, Skandalen
    - WANN NICHT: Bei Übergängen, Erklärungen, Allgemeinwissen
    - NATÜRLICHER FLUSS wichtiger als Quellenanzahl!

    QUELLENANGABEN-BALANCE (Fingerspitzengefühl):
    - NICHT jeder Satz braucht eine Quelle - das wirkt überladen!
    - PRO ABSATZ: Maximal 1-2 strategische Quellenangaben
    - ZITATE: Jedes echte Zitat braucht SOFORT eine Quellenangabe
    - FAKTEN: Wichtige Daten/Zahlen mit Quelle, aber nicht übertreiben
    - NATÜRLICHER FLUSS: Quelle dort einfügen, wo sie organisch passt

{source_info}

ENTERTAINMENT-QUELLENTEXT:
{article_text}

KRITISCHE ERINNERUNG 
- JEDES Celebrity-Zitat braucht SOFORT eine Quellenangabe
- Pro Absatz EINE strategische Quellenangabe bei wichtigen Entertainment-Facts
- Qualität vor Quantität bei Quellenangaben
- ALLE Zitate müssen ins Deutsche übersetzt werden

ANTI-HALLUZINATIONS-REGEL FÜR TITEL/UNTERTITEL:
- NIEMALS vergangene Ereignisse als aktuell darstellen
- UNTERSCHEIDE klar: "plant Rückkehr" ≠ "feiert Comeback" 
- TIMELINE beachten: Was ist passiert vs. was ist geplant
- TITEL muss zum aktuellen Stand passen, nicht zu Zukunftsplänen
- BEISPIEL: "Baby-Freude bei TV-Star" statt "TV-Comeback gefeiert"

Erstellen Sie einen SEO-optimierten journalistischen Artikel, der Informationen aus dem Artikelentwurf zusammenfasst, der mehrere Quellen enthalten kann. Behalten Sie beim Umschreiben alle Fakten und Daten bei und verwenden Sie einzigartige Satzstrukturen und Formulierungen, um eine zusammenhängende Erzählung zu erstellen, die sich natürlich zwischen verschiedenen Quellenmaterialien bewegt.

Wichtig: Direkte Zitate aus dem Entwurf müssen exakt und unverändert übernommen werden, wenn sie im neuen Artikel verwendet werden. Es darf keine Änderung an der Wortwahl, Grammatik oder am Satzbau der Zitate vorgenommen werden. Du kannst jedoch entscheiden, welche Zitate in den Artikel aufgenommen werden sollen, es müssen nicht alle sein. 
WICHTIG: ALLE ZITATE MÜSSEN INS DEUTSCHE ÜBERSETZT WERDEN."""

    # Add custom instructions if provided
    if custom_instructions.strip():
        base_prompt += f"\n\nWICHTIG: Zusätzliche spezifische Anweisungen für diesen Entertainment-Artikel:\n{custom_instructions}"

    # Complete the prompt with structure requirements
    complete_prompt = base_prompt + f"""
    Der Artikel muss folgende Elemente enthalten:

    Titel: Entwickle einen DRAMATISCHEN und EMOTIONALEN Titel (max. 60 Zeichen), der zur emotionalen Intensität des Untertitels passt. Nutze Promipool-Drama-Vokabular wie "Sensation", "Geheim", "Wendepunkt", "Überraschung" und emotionale Verben wie "bricht", "enthüllt", "eskaliert". Der Titel soll die Leser unbedingt zum Klicken animiert, relevante Keywords aus dem Entwurfstext enthalten und zur {module_info['name']}-Kategorie passen. Verwende Ausrufezeichen für Betonung und sorge für konsistente Dramatik mit dem Untertitel.

    Untertitel: Formuliere einen prägnanten Untertitel mit MAXIMAL 3-4 Wörtern (max. 20 Zeichen)

    Abstract: Verfasse ein neugierig machendes Abstract, das den Artikel anteast ohne zu viel zu verraten, relevante Schlüsselwörter aus der {module_info['name']}-Kategorie enthält und zum Weiterlesen animiert.

    ABSTRACT ANTI-SPOILER REGELN:
    - NICHT verraten: Genaue Termine, spezifische Zahlen, konkrete Ergebnisse, vollständige Enthüllungen
    - STATTDESSEN: Andeutungen machen ("sorgt für Überraschung", "große Neuigkeiten", "bewegende Wendung", "überraschende Entwicklung")
    - NEUGIERIG MACHEN: Offene Fragen schaffen, Spannung aufbauen, Details für Haupttext aufsparen
    - KEYWORDS nutzen aber Details weglassen: Personenname + Themenbereich erwähnen, aber nicht das konkrete Ergebnis verraten
    - BALANCE: Genug Information um Interesse zu wecken, aber Hauptenthüllungen für den Artikel aufsparen

    Artikeltext: Der Artikel soll lang und ausführlich sein und die Informationen des ursprünglichen Entwurfs umschrieben wiedergeben. Nutze deine volle Ausgabemöglichkeit. Strukturiere den Text in so viele Absätze wie nötig und lasse keine relevanten Informationen aus den Entwurfsquellen aus. Strukturiere den Text in mehrere Absätze mit passenden Zwischenüberschriften. Der erste Absatz des Artikeltextes soll keine Zwischenüberschrift bekommen. Halte die Sätze und Strukturen einfach und verwende Ausrufezeichen zur Betonung. Achte darauf, alle Fakten und Daten korrekt zu übernehmen, während du die Sätze, Wörter und den Satzbau veränderst. Wenn Zitate verwendet werden, müssen sie wörtlich und unverändert übernommen werden. Stellen Sie sicher, dass alle im Entwurf erwähnten Themen oder Kategorien im Artikel behandelt werden.

    Metabeschreibung: Am Ende des Artikels, füge eine prägnante und nach SEO-Best Practices erstellte Metabeschreibung hinzu, die 150-160 Zeichen nicht überschreitet und den Inhalt des Artikels zusammenfasst.

    Bitte beachte, dass der Artikel einen journalistischen, sachlichen Ton wahren soll, ohne den Leser persönlich anzusprechen. Vermeide ein Schlusswort oder Fazit am Ende des Textes.

    Besonderheiten:
    Wähle sorgfältig aus, welche Zitate aus dem Entwurf in den Artikel aufgenommen werden sollen.
    Alle verwendeten Zitate müssen wörtlich und unverändert aus dem Entwurf übernommen werden.
    Übersetze Zitate immer in deutsche Sprache.
    WICHTIG: SETZE IMMER DIE KOMBINATION AUS VOR- UND NACHNAME.
    WICHTIG: LASSE KEINE RELEVANTEN INFORMATIONEN AUS DEN ENTWURFSQUELLEN AUS
    WICHTIG: Verwende korrekte Quellenangaben kursiv: *Bild.de*, *RTL.de*, *Gala.de*
    Der restliche Artikel soll vollständig umgeschrieben werden.
    Versuche Dopplungen im Text zu vermeiden, indem du verwandte Themen und Informationen jeweils nur einmal explizit darstellst und in späteren Absätzen gegebenenfalls indirekt darauf verweist.

    Checkliste:
    Sind alle Zitate korrekt ins Deutsche übersetzt?
    Sind die Zitate unverändert übernommen worden?
    Ist überall Vor- und Nachname gesetzt worden?
    Sind alle relevanten Informationen aus den Entwurfsquellen übernommen wurden?
    Sind korrekte Quellenangaben kursiv hervorgehoben worden?
    Wurden nur die verfügbaren echten Zitate verwendet?

    Der Artikel muss die folgenden Komponenten beinhalten und genau so formatiert sein:

    Titel:
    [Dein Titel ohne Formatierung]

    Untertitel:
    [Dein Untertitel ohne Formatierung]

    Abstract:
    [Dein Abstract ohne Anführungszeichen und ohne Formatierung]

    Artikeltext:
    [Hier kommt der Haupttext ohne Bulletpoints]

    ### [Erste Zwischenüberschrift]
    [Textabsatz mit korrekten Quellenangaben]

    ### [Zweite Zwischenüberschrift]
    [Textabsatz mit korrekten Quellenangaben]

    Formatierungsregeln für den Artikeltext:
    - Verwende ### für Zwischenüberschriften (WICHTIG: Genau drei Hashzeichen)
    - Lasse immer eine Leerzeile zwischen Absätzen
    - Keine Sternchen (*) für Formatierung
    - Keine Anführungszeichen außer bei direkten Zitaten und Quellenangaben
    - Keine Zwischenüberschrift vor dem ersten Absatz
    - Quellenangaben immer kursiv: laut *Bild.de*, so *RTL.de* berichtet
    - WICHTIG: KEINE Sternchen (**) um Titel, Untertitel, Abstract oder Metabeschreibung
    - Die Komponenten-Labels (Titel:, Untertitel:, etc.) OHNE jegliche Formatierung

    Metabeschreibung:
    [Deine Metabeschreibung]

    Keywords:
    [Deine Keywords inkl. {', '.join(module_info['hashtags'][:2])} relevante Begriffe]

    Hier ist der Text des Entwurfsartikels: {article_text}"""

    result = generate_text(complete_prompt)
    result = convert_source_quotes_to_german(result)
    return result

def process_text_for_social_linkedin(result_text):
    prompt2 = f"""Erstelle einen LinkedIn-Post basierend auf dem folgenden Artikeltext mit dem thematischen Fokus auf Wirtschaft, Finanzen, Arbeitswelt, Karriere, Technologie, Innovation, Nachhaltigkeit oder Lifestyle. Der Post sollte folgende Elemente enthalten: 

    1.Einen einprägsamen und klickstarken Titel-Hook, der den Hauptaspekt des Artikels hervorhebt (max. 150 Zeichen).
    2.Eine kurze Zusammenfassung der wichtigsten Lerninhalte des Artikels (max. 400 Zeichen).
    3.Ein bis zwei relevante Zitate oder Daten aus dem Artikel (max. 150 Zeichen).
    4.Einen Bezug zu aktuellen Trends der oben genannten Themen (max. 150 Zeichen).
    5.Drei bis fünf passende, aus dem Artikelinhalt abgeleitete Hashtags.
    6.Eine zum Thema passende Frage oder einen Call-to-Action am Ende des Posts, um die Interaktion (Kommentare, Teilen) zu fördern (max. 150 Zeichen).
    7.Sprich die Leser direkt an, vermeide aber unbedingt die Wörter Du und Sie bei der Ansprache. Verwende zwei bis drei passenden Emojis an Schlüsselstellen, um die Aufmerksamkeit zu erhöhen und den Post visuell ansprechender zu gestalten.

    Die Gesamtlänge des Posts sollte 900-1100 Zeichen nicht überschreiten.

    Hier ist der Text des Artikels: {result_text}"""

    return generate_text(prompt2)

def process_text_for_social_facebook(result_text):  
    prompt3 = f"""Erstelle einen Facebook-Post basierend auf dem folgenden Artikeltext mit dem thematischen Fokus auf Wirtschaft, Finanzen, Arbeitswelt, Karriere, Technologie, Innovation, Nachhaltigkeit oder Lifestyle. Der Post sollte folgende Elemente enthalten: 

    1.Jedes Posting beginnt mit einem prägnanten Satz oder einer Überschrift, die das Hauptthema des Beitrags zusammenfasst. Diese sind oft provokativ oder aufmerksamkeitserregend gestaltet.
    2.Nach der Überschrift folgt eine kurze Einleitung, die das Thema des Artikels weiter ausführt und oft eine Zusammenfassung der wesentlichen Punkte bietet.In der Regel ein bis drei Sätze lang
    3.Die Tonalität der Postings ist überwiegend sachlich und informativ, richtet sich jedoch klar an ein Publikum, das sich für Wirtschaftsthemen interessiert. Einige Beiträge haben einen engagierten Ton, der Leser zum Nachdenken anregen oder Diskussionen fördern soll.
    In einigen Fällen wird eine provokative Sprache verwendet, um Kontroversen oder Debatten zu entfachen, wie z.B. bei Themen über Sexismus oder Arbeitsmarktprobleme.
    4. Die Postings beziehen sich auf aktuelle Ereignisse und Trends, was zeigt, dass die Seite bemüht ist, immer up-to-date zu bleiben und relevante Inhalte zu liefern. .
    5.Drei bis fünf passende, aus dem Artikelinhalt abgeleitete Hashtags.
    6.Eine zum Thema passende Frage oder einen Call-to-Action am Ende des Posts, um die Interaktion (Kommentare, Teilen) zu fördern (max. 150 Zeichen).
    7.Sprich die Leser direkt an, vermeide aber unbedingt die Wörter Du und Sie bei der Ansprache. Verwende zwei bis drei passenden Emojis an Schlüsselstellen, um die Aufmerksamkeit zu erhöhen und den Post visuell ansprechender zu gestalten.

    Die Gesamtlänge des Posts sollte 450 Zeichen nicht überschreiten. 
    Hier ist der Text des Artikels: {result_text}"""

    return generate_text(prompt3)


def send_telegram_notification(input_data, result):
    """
    Sends Telegram notification using credentials from Streamlit secrets.
    Requires 'telegram_bot_token' and 'telegram_channel_id' in secrets.toml
    """
    # Load from Streamlit secrets instead of hardcoding
    try:
        bot_token = st.secrets.get("telegram_bot_token")
        channel_id = st.secrets.get("telegram_channel_id")

        if not bot_token or not channel_id:
            st.warning("⚠️ Telegram credentials not configured in secrets.toml")
            return
    except Exception as e:
        st.warning(f"⚠️ Telegram secrets not available: {str(e)}")
        return

    if isinstance(input_data, list):
        # It's a list of URLs
        input_text = "URLs:\n" + "\n".join(input_data)
    else:
        # It's a text input
        input_text = "USER_TEXT"

    message_text = f"{input_text}\n\nResult:\n{result}"

    api_url = f'https://api.telegram.org/bot{bot_token}/sendMessage'

    data = {
        'chat_id': channel_id,
        'text': message_text
    }

    try:
        response = requests.post(api_url, data=data)
        if response.status_code == 200:
            st.success("TN sent.")
        else:
            st.warning(f"Failed to send TN. Status code: {response.status_code}")
    except Exception as e:
        st.error(f"An error occurred while sending TN: {e}")

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

def process_direct_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        article_text = article.text
    except Exception as e:
        st.warning(f"Failed to process URL with newspaper3k: {e}. Trying Jina.ai...")
        try:
            article_text = get_jina_content(url)
        except Exception as jina_error:
            return f"An error occurred while processing the URL: {jina_error}", None

    seo_article = process_text_for_seo(article_text)
    return seo_article, article_text

def process_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def main():
    col1, col2, col3 = st.columns(3)

    with col1:
        st.title("Generate Article from Multiple Sources")
        
        st.subheader("Input URLs")
        num_url_inputs = st.number_input("Number of URLs to process", min_value=0, max_value=5, value=1)
        urls = []
        for i in range(num_url_inputs):
            url = st.text_input(f"Enter URL {i+1}", key=f"url_{i}")
            if url:
                urls.append(url)
        
        user_text = st.text_area("Or enter the text you'd like to rewrite:", height=200)
        # Add custom instructions textarea
        custom_instructions = st.text_area(
            "Custom Instructions (Optional)",
            help="Add specific instructions for tone, style, focus areas, or any other special requirements for the article generation.",
            placeholder="Example: 'Focus more on technical details' or 'Emphasize sustainability aspects'",
            height=150
        )
        
        uploaded_file = st.file_uploader("Or upload a PDF file:", type="pdf")
        
        st.warning("If URL scraping doesn't work, we'll try using Jina.ai as a fallback.", icon="⚠️")
        
        if st.button("Generate Article from Sources"):
            with st.spinner('Creating Article from the provided data...'):
                result = original_text = None
                source = ""
                
                if urls:
                    original_text, url_contents = process_multiple_urls(urls)
                    source = ", ".join(urls)
                
                if user_text.strip():
                    if original_text:
                        original_text += "\n\n" + user_text.strip()
                        source += " and user provided text"
                    else:
                        original_text = user_text.strip()
                        source = "User provided text"
                
                if uploaded_file is not None:
                    pdf_text = process_pdf(uploaded_file)
                    if original_text:
                        original_text += "\n\n" + pdf_text
                        source += " and uploaded PDF"
                    else:
                        original_text = pdf_text
                        source = "Uploaded PDF"
                
                if original_text:
                    # Generate 1. Draft
                    source_info = create_source_info_promipool(urls, uploaded_file, bool(user_text.strip()), url_contents if 'url_contents' in locals() else {})
                    result = process_text_for_seo_enhanced_promipool(original_text, source_info, custom_instructions)
                    
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
                            # Initial Artikel generieren
                            title, subtitle, abstract, content, meta = extract_article_components(result)
                            st.session_state['title'] = title
                            st.session_state['subtitle'] = subtitle
                            st.session_state['abstract'] = abstract
                            st.session_state['content'] = content
                            st.session_state['meta'] = meta
                            
                            # Artikel Container erstellen und speichern
                            article_container = display_article()
                            
                            # CMS-Optionen
                            send_article_to_pp_fragment()
                            
                            # Bearbeitungsoptionen mit Container übergeben
                            edit_article(article_container)
                                        
                        # Update Google Sheet
                        current_date = time.strftime("%Y-%m-%d")
                        current_time = time.strftime("%H:%M:%S")
                        #success, message = update_google_sheet(
                        #    current_date, 
                        #    current_time, 
                        #    source, 
                        #    original_text, 
                        #    result, 
                        #    "Zusatz-ArticleURLs"
                        #)
                        
                        #if not success:
                        #    st.warning(f"Warning: {message}")
                        #elif "truncated" in message.lower():
                        #    st.info(message)
                        
                    
                        #send_telegram_notification(urls if urls else "USER_TEXT", result) 
                        
                        if st.query_params.get("dt") == "1":
                            with st.expander("Debug Output:"):
                                st.subheader("Debug Output:")
                                st.write(f"**Scraped Content:** {original_text}")
                        
                        # linkedin = process_text_for_social_linkedin(result)
                        # st.title("LinkedIn Post:")
                        # st.write(linkedin)
                        # facebook = process_text_for_social_facebook(result)
                        # st.title("Facebook Post:")
                        # st.write(facebook)
                                        
                else:
                    st.error("No content to process. Please provide URLs, enter text, or upload a PDF file.")

if __name__ == "__main__":
    main()