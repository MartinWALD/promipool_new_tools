from openai import OpenAI
import time
import anthropic
from rich import print
import requests
import pandas as pd 
import streamlit as st
from newspaper import Article
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse
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

wp_url = "https://www.business-punk.com/wp-json/wp/v2/posts"
wp_auth_key = st.secrets["wp_bpm"]  # Replace with your actual base64 encoded authorization key
category_ids = [83]  # Category Ablage

# Set OpenAI key from Streamlit secrets
#openai.api_key = st.secrets["openai"]

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

#client = gspread.authorize(credentials)

# Initialize the Google Sheet and worksheet
#spreadsheet = client.open("bpm_logs")  # Replace with your actual sheet name
#worksheet = spreadsheet.worksheet("Article")  # Replace with your actual worksheet name

# Streamlit UI layout
col1, col2, col3 = st.columns(3)

def update_google_sheet(date, time, source, original_text, result_text, linkedin):
    worksheet.append_row([date, time, source, original_text, result_text, linkedin])

def create_source_info(urls, uploaded_file=None, user_text_provided=False, url_contents=None):
    """
    Erstellt erweiterte Quelleninfo für bessere Zitierung und Content-Verteilung im Business Punk Artikel.
    
    Args:
        urls: Liste der URLs
        uploaded_file: Hochgeladene Datei (optional)
        user_text_provided: Bool ob Benutzertext vorhanden
        url_contents: Dict mit URL -> Content Mapping
        
    Returns:
        str: Erweiterte Quelleninfo mit Content-Verteilungsanweisungen für Business Punk
    """
    
    def extract_domain_info(url):
        """Extrahiert Domain-Informationen und bestimmt Business-relevante Quellennamen"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            
            # Business Punk relevante Quellentyp-Erkennung
            business_source_mapping = {
                'lto.de': ('Legal Tribune Online', 'Legal Tribune Online', 'Rechts- und Wirtschaftsnachrichten'),
                'businessinsider': ('Business Insider', 'Wirtschaftsmagazin Business Insider', 'Startup-News und Wirtschaftstrends'),
                'business-insider': ('Business Insider', 'Wirtschaftsmagazin Business Insider', 'Startup-News und Wirtschaftstrends'),
                'techcrunch': ('TechCrunch', 'Tech-Magazin TechCrunch', 'Startup-Nachrichten und Tech-Innovation'),
                'wired': ('Wired', 'Tech-Magazin Wired', 'Technologie und digitale Transformation'),
                'forbes': ('Forbes', 'Wirtschaftsmagazin Forbes', 'Unternehmertum und Leadership-Insights'),
                'entrepreneur': ('Entrepreneur', 'Entrepreneur Magazine', 'Gründertum und Business-Strategien'),
                'fastcompany': ('Fast Company', 'Business-Magazin Fast Company', 'Innovation und moderne Arbeitskultur'),
                'handelsblatt': ('Handelsblatt', 'Handelsblatt', 'deutsche Wirtschaftsnachrichten und Finanzanalysen'),
                'manager-magazin': ('Manager Magazin', 'Manager Magazin', 'Management-Trends und Karriereentwicklung'),
                'gruenderszene': ('Gründerszene', 'Startup-Magazin Gründerszene', 'deutsche Startup-Szene und Gründernews'),
                'finance-forward': ('Finance Forward', 'Fintech-Magazin Finance Forward', 'Fintech-Innovationen und Digital Finance'),
                'omr': ('OMR', 'Online Marketing Rockstars', 'Digital Marketing und New Economy'),
                'xing': ('Xing', 'Business-Netzwerk Xing', 'Karriere-Insights und Professional Networking'),
                'linkedin': ('LinkedIn', 'Business-Netzwerk LinkedIn', 'Professional Content und Thought Leadership'),
                'spiegel': ('Spiegel', 'Nachrichtenmagazin Spiegel', 'gesellschaftspolitische Einordnung und Hintergrundanalysen'),
                'welt': ('Welt', 'Tageszeitung Die Welt', 'aktuelle Wirtschaftsnachrichten und politische Entwicklungen'),
                'faz': ('FAZ', 'Frankfurter Allgemeine Zeitung', 'Wirtschaftsanalysen und Finanzmarktberichte'),
                'sueddeutsche': ('Süddeutsche Zeitung', 'Süddeutsche Zeitung', 'investigative Wirtschaftsberichterstattung'),
                'zeit': ('Zeit', 'Wochenzeitung Die Zeit', 'tiefgreifende Wirtschaftsanalysen und Gesellschaftstrends'),
                'venture-capital': ('VC-Magazin', 'Venture Capital Magazin', 'Investment-Trends und Startup-Finanzierung'),
                'crunchbase': ('Crunchbase', 'Startup-Datenbank Crunchbase', 'Unternehmens- und Investitionsdaten'),
                'pitchbook': ('PitchBook', 'Investment-Datenbank PitchBook', 'Private Equity und Venture Capital Daten'),
                'reddit': ('Reddit', 'Online-Forum Reddit', 'Community-Diskussionen und Insider-Perspektiven'),
                'twitter': ('Twitter/X', 'Social Media Plattform X', 'Real-time Business-Updates und Meinungsführer'),
                'medium': ('Medium', 'Publishing-Plattform Medium', 'Thought Leadership und Expertenmeinungen')
            }
            
            for key, (name, description, content_focus) in business_source_mapping.items():
                if key in domain.lower():
                    return domain, name, description, content_focus
            
            # Fallback für unbekannte Business-relevante Domains
            return domain, domain, f"Business-Quelle {domain}", "spezifische Fachinformationen"
            
        except Exception:
            return url, url, f"Online-Quelle {url}", "allgemeine Informationen"
    
    if not url_contents:
        url_contents = {}
    
    source_info = "QUELLENVERZEICHNIS FÜR BUSINESS PUNK ARTIKEL:\n"
    source_counter = 1
    content_guidance = []
    source_names = []  # Sammle saubere Quellennamen
    
    # URLs verarbeiten mit Business-fokussierter Content-Analyse
    for url in urls:
        if url.strip():
            domain, source_name, source_description, content_focus = extract_domain_info(url)
            content = url_contents.get(url, "")
            
            source_info += f"Quelle {source_counter}: {source_description} ({domain})\n"
            source_names.append(source_name)  # Sammle Namen für Komma-Liste
            
            # Business Punk spezifische Content-Analyse
            if content:
                content_length = len(content.split())
                if content_length > 800:
                    content_weight = "umfassende Business-Insights"
                elif content_length > 400:
                    content_weight = "detaillierte Marktanalysen"
                else:
                    content_weight = "prägnante Business-Facts"
                    
                # Business-relevante Content-Typen erkennen
                has_quotes = '"' in content or "'" in content
                has_numbers = any(char.isdigit() for char in content)
                has_business_terms = any(term in content.lower() for term in [
                    'startup', 'investment', 'funding', 'revenue', 'profit', 'growth', 
                    'innovation', 'disruption', 'digital transformation', 'leadership',
                    'ceo', 'founder', 'entrepreneur', 'venture capital', 'ipo'
                ])
                has_financial_data = any(term in content.lower() for term in [
                    'million', 'billion', 'euro', 'dollar', 'prozent', 'umsatz', 'gewinn'
                ])
                
                content_types = []
                if has_quotes:
                    content_types.append("Expertenzitate")
                if has_financial_data:
                    content_types.append("Finanzdaten")
                if has_business_terms:
                    content_types.append("Business-Insights")
                if has_numbers:
                    content_types.append("Kennzahlen")
                    
                guidance = f"   → Nutze {source_name} für {content_focus}"
                if content_types:
                    guidance += f" (enthält: {', '.join(content_types)})"
                guidance += f" - {content_weight} verfügbar"
                
                content_guidance.append(guidance)
            
            source_counter += 1
    
    # Uploaded file
    if uploaded_file is not None:
        file_type = uploaded_file.type if hasattr(uploaded_file, 'type') else 'Dokument'
        source_info += f"Quelle {source_counter}: Hochgeladenes {file_type}\n"
        source_names.append("Hochgeladenes Dokument")
        content_guidance.append(f"   → Nutze das Dokument für interne Business-Daten und Strategiepapiere")
        source_counter += 1
    
    # User text
    if user_text_provided:
        source_info += f"Quelle {source_counter}: Nutzereingabe\n"
        source_names.append("Nutzereingabe")
        content_guidance.append(f"   → Nutze die Nutzereingabe für zusätzliche Business-Kontexte")
        source_counter += 1
    
    # Business Punk spezifische Content-Verteilungsanweisungen
    if content_guidance:
        source_info += "\nCONTENT-VERTEILUNGSANWEISUNGEN FÜR BUSINESS PUNK STIL:\n"
        source_info += "\n".join(content_guidance)
        source_info += "\n\nWICHTIG FÜR BUSINESS PUNK: Verteile die Informationen gleichmäßig über alle verfügbaren Quellen. "
        source_info += "Jeder Artikel-Abschnitt sollte mindestens 2-3 verschiedene Quellen nutzen für maximale "
        source_info += "Glaubwürdigkeit und ausgewogene Perspektiven. Priorisiere Business-relevante Insights.\n"
        
        # Business Punk Anti-Monotonie-Regeln
        source_info += "\nBUSINESS PUNK ZITIERREGELN:\n"
        source_info += "- Wechsle strategisch zwischen Startup-, Finanz- und Mainstream-Medien\n"
        source_info += "- Nutze Tech-Quellen (TechCrunch, Wired) für Innovationsaspekte\n"
        source_info += "- Verwende Wirtschaftsmedien (Handelsblatt, FAZ) für Marktanalysen\n"
        source_info += "- Setze Startup-Medien (Gründerszene, OMR) für Szene-Insights ein\n"
        source_info += "- Kombiniere internationale und deutsche Perspektiven\n"
        source_info += "- Bevorzuge Primärquellen für Unternehmensdaten und CEO-Statements\n"
        source_info += "- Nutze Social Media-Quellen für aktuelle Trends und Community-Meinungen\n"
    
    # KRITISCH: Kommagetrennte Quellenliste hinzufügen
    if source_names:
        formatted_sources = ', '.join([f'"{name}"' for name in source_names])
        source_info += f"\n\nQUELLEN FÜR ARTIKEL:\n{formatted_sources}"
    
    return source_info

def process_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

#new OpenAi Client, old model: gpt-4o, gpt-4o-2024-08-06, gpt-4o-mini
def generate_text(prompt, model="gpt-4o", temperature=0.5, max_retries=3):
    client = OpenAI(api_key=st.secrets["openai"], max_retries=max_retries)
    messages = [{"role": "user", "content": prompt}]
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()

# Funktion zum Generieren von Text mit der Claude API  - neu claude-3-7-sonnet-20250219, alt claude-3-5-sonnet-20240620
CLAUDE_API_KEY = st.secrets["claude_pp"]
def generate_text_claude(prompt: str) -> str:
    """
    Generiere Text mit der Claude API.
    """
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=8192,
        temperature=0.5,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return response.content[0].text

@st.experimental_fragment
def api_send_fragment(title, abstract, content, meta, sources="", reality_check="", faqs=""):
    if st.button("Send to API"):
        with st.spinner("Sending data to API..."):
            content_with_additions = content
        
            # FAQs hinzufügen (als WordPress-Liste)
            if faqs:
                content_with_additions += f"\n\n{faqs}"
        
            # VEREINFACHTE Quellen-Formatierung
            if sources:
                print(f"DEBUG: Verarbeite Quellen: {sources}")
                
                # Erwarte jetzt direkt das Format: "Quelle1", "Quelle2", "Quelle3"
                sources_formatted = f"<em>Quellen: {sources}</em>"
                content_with_additions += f"\n\n<!-- wp:paragraph -->\n<p>{sources_formatted}</p>\n<!-- /wp:paragraph -->"
                
                print(f"DEBUG: Finale Quellen-Formatierung: {sources_formatted}")
                
            response = create_wordpress_draft(wp_url, wp_auth_key, title, content_with_additions, category_ids, abstract, meta)
            
            st.subheader("API Response Details")
            st.write(f"Status Code: {response.get('status_code', 'N/A')}")
            
            if "error" in response:
                st.error(f"Error: {response['error']}")
            else:
                st.success(f"Success: {response.get('response_json', {}).get('message', 'Data sent successfully')}")

def create_wordpress_draft(wp_url, wp_auth_key, title, content, category_ids, abstract, meta):
    # Prepare the content with the abstract included
    #full_content = f'<!-- wp:paragraph -->\n<p><strong>Abstract:</strong> {abstract}</p>\n<!-- /wp:paragraph -->\n\n{content}'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {wp_auth_key}'
    }
    data = {
        'title': title,
        'content': content,
        'status': 'draft',
        'categories': category_ids,
        #'excerpt': abstract,
        'meta': {
            '_yoast_wpseo_metadesc': meta  # Using the extracted meta description
        }
    }
    response = requests.post(wp_url, json=data, headers=headers)
    if response.status_code in (200, 201):
        try:
            response_json = response.json()
            return {
                "status_code": response.status_code,
                "response_json": response_json,
                "response_text": response.text,
                "response_headers": dict(response.headers)
            }
        except json.JSONDecodeError as e:
            return {"error": "Invalid JSON in the response", "response_text": response.text}
    else:
        return {"error": "HTTP error", "status_code": response.status_code}

def remove_markdown(text):
    """
    Erweiterte Funktion zum Entfernen von Markdown-Formatierung
    """
    if not text:
        return text
        
    # Entferne Markdown-URLs
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1', text)
    # Entferne Markdown-Überschriften
    text = re.sub(r'^\#{1,6}\s*(.+)', r'\1', text, flags=re.MULTILINE)
    # Entferne einfache Markdown-Formatierungen
    text = re.sub(r'\*{1,2}([^\*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'\_{1,2}([^\_]+)\_{1,2}', r'\1', text)
    # Entferne Code-Zeichen
    text = text.replace('`', '')
    # Entferne Blockquotes
    text = text.replace('> ', '')
    return text

def extract_article_components(article_result):
    """
    KORRIGIERT: 
    - Beide Quellen-Patterns unterstützen
    - DEBUG hinzugefügt
    - Doppelte Zuweisungen entfernt
    """
    #print("=== DEBUGGING: Original Claude Output ===")
    #print(article_result[:2000])  # Mehr Text zeigen
    
    # KORRIGIERTE Patterns
    title_pattern = r"(?:##\s*\*\*Titel\*\*|\*\*Titel\*\*|\#\#\s*Titel)\s*(.*?)(?=\n\s*(?:##|\*\*|$)|\Z)"
    abstract_pattern = r"(?:##\s*\*\*Abstract\*\*|\*\*Abstract\*\*|\#\#\s*Abstract)\s*(.*?)(?=\n\s*(?:##|\*\*Artikel|\*\*Artikelbody|$)|\Z)"
    
    # FIX: Content stoppt VOR FAQs
    content_patterns = [
    # Stoppt vor Metabeschreibung (gewünscht)
    (r"(?:##\s*\*\*Artikelbody\*\*|\*\*Artikelbody\*\*|\#\#\s*Artikelbody)(.*?)(?=\n\s*(?:##\s*\*\*Metabeschreibung\*\*|\*\*Metabeschreibung\*\*|\#\#\s*Metabeschreibung))", re.DOTALL, "vor Metabeschreibung"),
    # Fallback: Stoppt vor FAQs
    (r"(?:##\s*\*\*Artikelbody\*\*|\*\*Artikelbody\*\*|\#\#\s*Artikelbody)(.*?)(?=\n\s*(?:##\s*\*\*Häufig gestellte Fragen\*\*|\*\*Häufig gestellte Fragen\*\*|\#\#\s*Häufig gestellte Fragen|\*\*FAQs\*\*|##\s*\*\*FAQs\*\*|\#\#\s*FAQs))", re.DOTALL, "vor FAQs"),
]
    
    meta_pattern = r"(?:##\s*\*\*Metabeschreibung\*\*|\*\*Metabeschreibung\*\*|\#\#\s*Metabeschreibung)\s*(.*?)(?=\n\s*(?:##|\*\*Keywords|$)|\Z)"
    keywords_pattern = r"(?:##\s*\*\*Keywords\*\*|\*\*Keywords\*\*|\#\#\s*Keywords)\s*(.*?)(?=\n\s*(?:##|\*\*Reality Check|\*\*Business Punk Check|\*\*Häufig gestellte Fragen|\*\*FAQs|$)|\Z)"
    
    # FAQs für separate WordPress-Liste
    faqs_pattern = r"(?:##\s*\*\*Häufig gestellte Fragen\*\*|\*\*Häufig gestellte Fragen\*\*|\#\#\s*Häufig gestellte Fragen|\*\*FAQs\*\*|##\s*\*\*FAQs\*\*|\#\#\s*FAQs)(.*?)(?=##\s*\*\*Quellen\*\*|\*\*Quellen\*\*|\#\#\s*Quellen|\Z)"
    
    # Quellen-Patterns
    sources_patterns = [
        r"## \*\*Quellen\*\*\s*(.*?)(?:\Z)",           # Prompt Format
        r"QUELLEN FÜR ARTIKEL:\n(.*?)(?:\n\n|\Z)",     # create_source_info Format
    ]

    # Extract components
    title = re.search(title_pattern, article_result, re.DOTALL)
    abstract = re.search(abstract_pattern, article_result, re.DOTALL)
    meta = re.search(meta_pattern, article_result, re.DOTALL)
    keywords = re.search(keywords_pattern, article_result, re.DOTALL)
    faqs = re.search(faqs_pattern, article_result, re.DOTALL)
    
    # DEBUGGING: Quellen-Suche mit mehreren Patterns
    sources = None
    sources_text = None
    sources_debug = "=== DEBUGGING: Quellen-Suche ===\n"
    
    for i, pattern in enumerate(sources_patterns):
        sources = re.search(pattern, article_result, re.DOTALL)
        sources_debug += f"Pattern {i+1}: {pattern}\n"
        sources_debug += f"Match: {sources is not None}\n"
        if sources:
            sources_text = sources.group(1).strip()  # Setze sources_text hier
            sources_debug += f"Inhalt: '{sources_text[:100]}...'\n"
            break
        sources_debug += "\n"
    
    print(sources_debug)
    
    if not sources:
        print("WARNUNG: Keine Quellen mit allen Patterns gefunden!")
        # Fallback: Suche nach bekannten Quellennamen im Text
        known_sources = ["Legal Tribune Online", "Zeit", "Welt", "Spiegel", "Handelsblatt", "Business Insider"]
        found_sources = []
        for source in known_sources:
            if source in article_result:  # Ohne Anführungszeichen suchen
                found_sources.append(source)
        
        if found_sources:
            sources_text = ', '.join(found_sources)  # Ohne Anführungszeichen
            print(f"FALLBACK: Gefundene Quellen im Text: {sources_text}")
        else:
            sources_text = None
            print("FALLBACK: Keine Quellen gefunden!")
    else:
        print(f"SUCCESS: Quellen extrahiert: '{sources_text}'")

    # Content extraction - mit Debug
    content = None
    for i, (pattern, flags, name) in enumerate(content_patterns):
        match = re.search(pattern, article_result, flags)
        print(f"Content Pattern {i+1} ({name}): {match is not None}")
        if match:
            content = match.group(1).strip()
            print(f"✅ Content erfolgreich extrahiert mit Pattern '{name}': {len(content)} Zeichen")
            break
    
    # Clean up components
    title = title.group(1).strip() if title else None
    abstract = abstract.group(1).strip() if abstract else None
    meta = meta.group(1).strip() if meta else None
    keywords = keywords.group(1).strip().split('\n* ') if keywords and keywords.group(1) else []
    
    # FAQ-Verarbeitung für WordPress-Liste
    if faqs:
        faqs_content = faqs.group(1).strip()
        # CLEANUP: Entferne ## am Ende
        faqs_content = re.sub(r'\s*#+\s*$', '', faqs_content)
        
        faqs_formatted = f'<!-- wp:heading {{\"level\":2}} -->\n<h2>Häufig gestellte Fragen</h2>\n<!-- /wp:heading -->\n\n'
        faqs_formatted += format_faqs_with_gutenberg(faqs_content)
    else:
        faqs_formatted = None
    
    # Keywords processing
    if keywords and isinstance(keywords, list) and len(keywords) == 1 and ',' in keywords[0]:
        keywords = [k.strip() for k in keywords[0].split(',')]

    # Bereinige Markdown-Formatierung
    title = remove_markdown(title) if title else None
    abstract = remove_markdown(abstract) if abstract else None
    meta = remove_markdown(meta) if meta else None
    sources_text = remove_markdown(sources_text) if sources_text else None
    
    # Remove any remaining '#' characters
    title = re.sub(r'\s*#+\s*$', '', title) if title else None
    abstract = re.sub(r'\s*#+\s*$', '', abstract) if abstract else None
    meta = re.sub(r'\s*#+\s*$', '', meta) if meta else None
    sources_text = re.sub(r'\s*#+\s*$', '', sources_text) if sources_text else None

    # Clean up content
    if content:
        content = re.sub(r'\s*#+\s*$', '', content, flags=re.MULTILINE)

    # Content-Formatierung (enthält Business Punk Check, aber KEINE FAQs)
    formatted_content = format_content_with_gutenberg_improved(content, abstract) if content else ""

    print(f"=== FINAL DEBUG ===")
    print(f"Sources text final: '{sources_text}'")

    # RETURN: 8 Komponenten
    return (title, abstract, formatted_content, meta, keywords, None, faqs_formatted, sources_text)

def format_content_with_gutenberg_improved(content, abstract):
    """
    OPTIMIERT: Erstellt pro H2-Überschrift genau 2 substantielle Absätze
    - Verhindert sehr kurze Absätze direkt nach Überschriften
    - Bessere optische Struktur für WordPress
    - Business Punk-gerechte Absatzlängen
    """
    import re
    
    formatted_content = ""

    # Füge den Abstract als Paragraph am Anfang hinzu
    if abstract:
        formatted_content += f'<!-- wp:paragraph -->\n<p><i>{abstract}</i></p>\n<!-- /wp:paragraph -->\n\n'

    if not content:
        return formatted_content
    
    # ERWEITERT: Bereinige beide Versionen
    content = re.sub(r'\*\*Reality Check\*\*', '## Business Punk Check', content)
    content = re.sub(r'\*\*Business Punk Check\*\*', '## Business Punk Check', content)
    
    # Überprüfe auf Überschriften
    if re.search(r'##\s+[^\n]+', content):
        print("Verarbeite Content mit ## Überschrift Format - 2 Absätze pro H2")
        
        # Teile in Abschnitte nach Überschriften
        sections = re.split(r'(##\s+[^\n]+)', content)
        
        # Einleitungsabsatz (falls vorhanden)
        if sections and not sections[0].strip().startswith('##'):
            intro = sections.pop(0).strip()
            if intro:
                # Einleitung: Falls sehr lang, in max. 2 Absätze teilen
                intro_paragraphs = create_intro_paragraphs(intro)
                formatted_content += intro_paragraphs
        
        # Verarbeite Überschrift-Inhalt-Paare
        i = 0
        while i < len(sections):
            # Überschrift
            if i < len(sections) and sections[i].strip().startswith('##'):
                heading = sections[i].replace('##', '').strip()
                formatted_content += f'<!-- wp:heading {{\"level\":2}} -->\n<h2>{heading}</h2>\n<!-- /wp:heading -->\n\n'
            
            # Inhalt - KERN: Genau 2 Absätze pro H2
            if i + 1 < len(sections) and not sections[i+1].strip().startswith('##'):
                paragraph_content = sections[i+1].strip()
                
                # NEUE FUNKTION: Erstelle genau 2 Absätze
                two_paragraphs = create_two_balanced_paragraphs(paragraph_content)
                formatted_content += two_paragraphs
                    
                i += 2
            else:
                i += 1
    else:
        # Fallback ohne Überschriften - in sinnvolle Absätze teilen
        balanced_paragraphs = create_balanced_paragraphs_without_headings(content)
        formatted_content += balanced_paragraphs
    
    return formatted_content

def format_faqs_with_gutenberg(faqs_text):
    """
    WORDPRESS-SICHER: FAQ-Listen ohne doppelte H2-Überschrift.
    FIX: Entferne ## am Ende
    """
    import re
    
    if not faqs_text:
        return ""
    
    # CLEANUP: Entferne ## am Ende des Textes
    faqs_text = re.sub(r'\s*#+\s*$', '', faqs_text.strip())
    
    # Erweiterte Pattern für bessere FAQ-Erkennung
    faq_patterns = [
        r'Frage\s*(\d+):\s*([^?]+\??)\s*\n([^F]+?)(?=Frage\s*\d+:|$)',  # "Frage X: ..."
        r'\*\*Frage\s*(\d+):\s*([^*]+)\*\*\s*\n([^*]+?)(?=\*\*Frage|\*\*|$)',  # "**Frage X: ...**"
        r'(\d+)\.\s*([^?]+\??)\s*\n([^0-9]+?)(?=\d+\.|$)'  # "1. Frage..."
    ]
    
    matches = []
    for pattern in faq_patterns:
        pattern_matches = re.findall(pattern, faqs_text, re.DOTALL)
        if pattern_matches:
            matches = pattern_matches
            break
    
    if not matches:
        print("FAQ Pattern nicht gematcht, verwende Fallback...")
        # FALLBACK: Bereinige ## auch hier
        formatted_faqs = ""
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', faqs_text) if p.strip()]
        for p in paragraphs:
            # Entferne ## am Ende jedes Absatzes
            p = re.sub(r'\s*#+\s*$', '', p)
            if p:  # Nur nicht-leere Absätze
                formatted_faqs += f'<!-- wp:paragraph -->\n<p>{p}</p>\n<!-- /wp:paragraph -->\n\n'
        return formatted_faqs
    
    print(f"FAQ Pattern matched! Gefunden: {len(matches)} FAQs")
    
    # OHNE H2-Überschrift (Claude generiert sie bereits)
    formatted_faqs = '<!-- wp:list {"className":"faq-list"} -->\n'
    formatted_faqs += '<ul class="faq-list">\n'
    
    for match in matches:
        if len(match) == 3:  # (nummer, frage, antwort)
            nummer, frage, antwort = match
            frage = frage.strip()
            antwort = antwort.strip()
            
            # Text bereinigen - ERWEITERT
            antwort = re.sub(r'\n+', ' ', antwort)  # Zeilenumbrüche entfernen
            antwort = re.sub(r'\s+', ' ', antwort)  # Mehrfache Leerzeichen
            antwort = re.sub(r'\s*#+\s*$', '', antwort)  # ## am Ende entfernen
            
            if antwort:  # Nur nicht-leere Antworten
                formatted_faqs += '<!-- wp:list-item -->\n'
                formatted_faqs += f'<li><strong>{frage}</strong><br>{antwort}</li>\n'
                formatted_faqs += '<!-- /wp:list-item -->\n\n'
    
    formatted_faqs += '</ul>\n'
    formatted_faqs += '<!-- /wp:list -->\n'
    
    return formatted_faqs

def create_two_balanced_paragraphs(text):
    """
    VERBESSERT: Längere, substantiellere Absätze + Bug-Fixes
    - Mindestens 3-4 Sätze pro Absatz (außer bei sehr kurzem Text)
    - Bereinigt leere Zeichen und Formatierungsfehler
    - Bessere Balance zwischen den Absätzen
    """
    import re
    
    if not text.strip():
        return ""
    
    # TEXT-BEREINIGUNG (gegen leere Gutenberg-Blöcke)
    text = clean_text_for_gutenberg(text)
    
    # Säubere Text und teile in Sätze
    sentences = split_into_sentences(text)
    
    # MINDEST-LÄNGEN für substantielle Absätze
    if len(sentences) <= 3:
        # Sehr kurzer Text: Ein Absatz (aber nur wenn wirklich sehr kurz)
        if len(text) < 200:  # Weniger als 200 Zeichen
            return f'<!-- wp:paragraph -->\n<p>{text}</p>\n<!-- /wp:paragraph -->\n\n'
        else:
            # Auch kurzen Text in 2 Absätze teilen für Konsistenz
            split_point = max(1, len(sentences) // 2)
            para1_text = ' '.join(sentences[:split_point])
            para2_text = ' '.join(sentences[split_point:])
            
            para1 = f'<!-- wp:paragraph -->\n<p>{para1_text}</p>\n<!-- /wp:paragraph -->\n\n'
            para2 = f'<!-- wp:paragraph -->\n<p>{para2_text}</p>\n<!-- /wp:paragraph -->\n\n'
            return para1 + para2
    
    # LÄNGERE ABSÄTZE: Neue Aufteilungslogik
    total_sentences = len(sentences)
    
    # GEÄNDERT: Aggressivere Aufteilung für längere Absätze
    if total_sentences <= 6:
        # 4-6 Sätze: 2-3 | Rest (mindestens 2 pro Absatz)
        split_point = max(2, min(3, total_sentences - 2))
    elif total_sentences <= 10:
        # 7-10 Sätze: 3-5 | Rest
        split_point = max(3, min(5, total_sentences - 3))
    elif total_sentences <= 14:
        # 11-14 Sätze: 4-6 | Rest  
        split_point = max(4, min(6, total_sentences - 4))
    else:
        # 15+ Sätze: ca. 45% im ersten Absatz (mehr als vorher)
        split_point = max(5, int(total_sentences * 0.45))
    
    # Finde optimalen Bruchpunkt
    optimal_split = find_optimal_split_point(sentences, split_point)
    
    # Erstelle die beiden Absätze
    paragraph1_sentences = sentences[:optimal_split]
    paragraph2_sentences = sentences[optimal_split:]
    
    # WICHTIG: Text-Bereinigung vor Formatierung
    para1_text = clean_paragraph_text(' '.join(paragraph1_sentences))
    para2_text = clean_paragraph_text(' '.join(paragraph2_sentences))
    
    # Formatiere als WordPress-Blöcke
    para1 = f'<!-- wp:paragraph -->\n<p>{para1_text}</p>\n<!-- /wp:paragraph -->\n\n'
    para2 = f'<!-- wp:paragraph -->\n<p>{para2_text}</p>\n<!-- /wp:paragraph -->\n\n'
    
    return para1 + para2


def find_optimal_split_point(sentences, target_split):
    """
    Findet den optimalen Bruchpunkt basierend auf logischen Übergängen
    """
    # Übergangswörter, die NICHT am Absatzanfang stehen sollten
    continuation_words = [
        'jedoch', 'aber', 'dennoch', 'trotzdem', 'außerdem', 'darüber hinaus',
        'andererseits', 'zudem', 'weiterhin', 'gleichzeitig', 'allerdings',
        'hingegen', 'vielmehr', 'deshalb', 'daher', 'folglich', 'somit'
    ]
    
    # Prüfe Bereich um target_split (±1 Position)
    possible_splits = []
    for pos in range(max(1, target_split - 1), min(len(sentences), target_split + 2)):
        if pos >= len(sentences):
            continue
            
        score = 0
        
        # Bonus: Wenn Position nahe am Ziel liegt
        distance_from_target = abs(pos - target_split)
        score += (2 - distance_from_target) * 10
        
        # Malus: Wenn nächster Satz mit Übergangswort beginnt
        if pos < len(sentences):
            next_sentence = sentences[pos].lower().strip()
            for word in continuation_words:
                if next_sentence.startswith(word):
                    score -= 20
                    break
        
        # Bonus: Ausgewogene Absatzlängen
        para1_length = sum(len(s) for s in sentences[:pos])
        para2_length = sum(len(s) for s in sentences[pos:])
        total_length = para1_length + para2_length
        
        if total_length > 0:
            ratio = para1_length / total_length
            # Ideal: 40-45% im ersten Absatz
            if 0.35 <= ratio <= 0.5:
                score += 15
            elif 0.3 <= ratio <= 0.55:
                score += 10
        
        possible_splits.append((pos, score))
    
    # Wähle Position mit höchstem Score
    if possible_splits:
        optimal_split = max(possible_splits, key=lambda x: x[1])[0]
        return optimal_split
    
    return target_split


def split_into_sentences(text):
    """
    VERBESSERTE Satztrennung - verhindert Probleme mit leeren Blöcken
    """
    import re
    
    # Bereinige Text zuerst
    text = clean_text_for_gutenberg(text)
    
    if not text.strip():
        return []
    
    # Schütze bekannte Abkürzungen (erweitert)
    replacements = {
        r'\bz\.\s*B\.': 'z_B_',
        r'\bd\.\s*h\.': 'd_h_',
        r'\bu\.\s*a\.': 'u_a_',
        r'\bvs\.': 'vs_',
        r'\bDr\.': 'Dr_',
        r'\bProf\.': 'Prof_',
        r'\bca\.': 'ca_',
        r'\betc\.': 'etc_',
        r'\binkl\.': 'inkl_',
        r'\bexkl\.': 'exkl_',
        r'\bggf\.': 'ggf_',
        r'\bmtl\.': 'mtl_',
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Trenne Sätze (verbessertes Pattern)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ„»"])', text)
    
    # Repariere Abkürzungen
    repair_map = {v: k.replace(r'\b', '').replace(r'\.', '.') for k, v in replacements.items()}
    
    sentences = [
        repair_sentence(s, repair_map).strip() 
        for s in sentences 
        if s.strip()
    ]
    
    # Filtere sehr kurze oder leere Sätze
    valid_sentences = []
    for sentence in sentences:
        # Mindestens 10 Zeichen und einen Buchstaben
        if len(sentence) >= 10 and re.search(r'[a-zA-ZäöüÄÖÜß]', sentence):
            valid_sentences.append(sentence)
    
    return valid_sentences


def create_balanced_paragraphs_without_headings(text):
    """
    VERBESSERT: Längere Absätze für Text ohne Überschriften
    """
    sentences = split_into_sentences(text)
    
    if len(sentences) <= 4:
        cleaned_text = clean_paragraph_text(text)
        return f'<!-- wp:paragraph -->\n<p>{cleaned_text}</p>\n<!-- /wp:paragraph -->\n\n'
    
    formatted_content = ""
    current_paragraph = ""
    sentence_count = 0
    target_sentences_per_paragraph = 5  # ERHÖHT von 4 auf 5
    
    for i, sentence in enumerate(sentences):
        current_paragraph += sentence + " "
        sentence_count += 1
        
        # Erstelle Absatz wenn Ziel erreicht oder letzter Satz
        should_break = (
            sentence_count >= target_sentences_per_paragraph or 
            i == len(sentences) - 1
        )
        
        if should_break:
            cleaned_para = clean_paragraph_text(current_paragraph)
            formatted_content += f'<!-- wp:paragraph -->\n<p>{cleaned_para}</p>\n<!-- /wp:paragraph -->\n\n'
            current_paragraph = ""
            sentence_count = 0
    
    return formatted_content

def clean_text_for_gutenberg(text):
    """
    NEUE FUNKTION: Bereinigt Text für saubere Gutenberg-Blöcke
    - Entfernt problematische Zeichen und Formatierungen
    - Verhindert leere Ziffern und HTML-Artefakte
    """
    import re
    
    # Entferne HTML-Reste und Formatierungs-Artefakte
    text = re.sub(r'<[^>]+>', '', text)  # HTML-Tags
    text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)  # HTML-Entities
    text = re.sub(r'\[([^\]]*)\]', '', text)  # Eckige Klammern mit Inhalt
    
    # Bereinige Markdown-Reste
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)  # **fett** oder ***fett***
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)    # __unterstrichen__
    text = re.sub(r'`([^`]+)`', r'\1', text)               # `code`
    
    # Bereinige Leerzeichen und Zeilenumbrüche
    text = re.sub(r'\n+', ' ', text)          # Mehrfache Zeilenumbrüche
    text = re.sub(r'\s+', ' ', text)          # Mehrfache Leerzeichen
    text = re.sub(r'\s*\.\s*\.', '.', text)   # Doppelte Punkte
    
    # Entferne führende/trailing Leerzeichen
    text = text.strip()
    
    return text


def clean_paragraph_text(text):
    """
    NEUE FUNKTION: Finale Bereinigung für einzelne Absätze
    - Verhindert leere Zeichen am Anfang/Ende
    - Korrigiert Satzzeichen-Probleme
    """
    import re
    
    text = text.strip()
    
    # Korrigiere Satzzeichen-Abstände
    text = re.sub(r'\s+([.!?,:;])', r'\1', text)  # Leerzeichen vor Satzzeichen entfernen
    text = re.sub(r'([.!?])\s*([.!?])', r'\1', text)  # Doppelte Satzzeichen
    
    # Stelle sicher, dass Sätze richtig enden
    if text and not text.endswith(('.', '!', '?')):
        text += '.'
    
    # Entferne problematische Start-/End-Zeichen
    text = re.sub(r'^[^\w"„«»\']+', '', text)  # Problematische Zeichen am Anfang
    text = re.sub(r'[^\w.!?"„«»\']+$', '', text)  # Problematische Zeichen am Ende
    
    return text

def repair_sentence(sentence, repair_map):
    """Repariert Abkürzungen in Sätzen"""
    for placeholder, original in repair_map.items():
        sentence = sentence.replace(placeholder, original)
    return sentence

def create_intro_paragraphs(intro_text, max_paragraphs=2):
    """
    VERBESSERTE Einleitungs-Behandlung mit längeren Absätzen
    """
    sentences = split_into_sentences(intro_text)
    
    if len(sentences) <= 2:
        # Sehr kurze Einleitung: 1 Absatz
        cleaned_text = clean_paragraph_text(intro_text)
        return f'<!-- wp:paragraph -->\n<p>{cleaned_text}</p>\n<!-- /wp:paragraph -->\n\n'
    
    elif len(sentences) <= 6:
        # Mittlere Einleitung: 2 Absätze (LÄNGER als vorher)
        split_point = max(2, len(sentences) // 2)  # Mindestens 2 Sätze pro Absatz
        
        para1_text = clean_paragraph_text(' '.join(sentences[:split_point]))
        para2_text = clean_paragraph_text(' '.join(sentences[split_point:]))
        
        para1 = f'<!-- wp:paragraph -->\n<p>{para1_text}</p>\n<!-- /wp:paragraph -->\n\n'
        para2 = f'<!-- wp:paragraph -->\n<p>{para2_text}</p>\n<!-- /wp:paragraph -->\n\n'
        return para1 + para2
    
    else:
        # Lange Einleitung: Intelligent in 2 längere Absätze teilen
        return create_two_balanced_paragraphs(intro_text)

# =============================================================================
# NEUE BUSINESS PUNK MODULE - EINFÜGEN NACH format_faqs_with_gutenberg()
# =============================================================================

def analyze_theme_module(article_text: str, source_info: str = "") -> str:
    """
    Analysiert Content und bestimmt das primäre Business Punk Themenmodul.
    ERWEITERT: Alle 10 Excel-Kategorien
    """
    
    # Kombiniere alle verfügbaren Texte
    full_text = (article_text + " " + source_info).lower()
    
    # ALLE 10 Business Punk Module aus Excel
    modules = {
        'WORK_WINNING': {
            'name': 'Work & Winning',
            'keywords': [
                'new work', 'karrierehacks', 'remote work', 'future skills', 'jobtrends', 
                'führungsstile', 'arbeitskultur', 'digital leadership', 'freelancer', 
                'work-life-balance', 'karriere', 'führung', 'leadership', 'chef', 'boss', 
                'manager', 'arbeit', 'job', 'homeoffice', 'büro', 'team', 'mitarbeiter', 
                'angestellt', 'arbeitsplatz', 'produktivität', 'meeting', 'zoom', 'agile', 
                'scrum', 'hybrid', 'flexibel', 'arbeitszeit', 'vorgesetzt'
            ],
            'high_priority': ['new work', 'remote work', 'digital leadership', 'work-life-balance']
        },
        
        'TECH_TRENDS': {
            'name': 'Tech & Trends',
            'keywords': [
                'künstliche intelligenz', 'digital disruption', 'tech-revolution', 
                'future of business', 'blockchain', 'machine learning', 'robotik', 
                'digitalisierung', 'ki-tools', 'metaverse', 'ki', 'ai', 'technologie', 
                'digital', 'innovation', 'tech', 'software', 'app', 'algorithmus', 
                'daten', 'cloud', 'automation', 'roboter', 'chatgpt', 'openai', 
                'tesla', 'apple', 'google', 'microsoft', 'amazon', 'meta', 'nvidia'
            ],
            'high_priority': ['ki', 'künstliche intelligenz', 'digital disruption', 'blockchain']
        },
        
        'STARTUP_SCALING': {
            'name': 'Startup & Scaling',
            'keywords': [
                'startups', 'gründerszene', 'disruptoren', 'business-hacks', 
                'innovationstreiber', 'unicorns', 'venture capital', 'seed-funding', 
                'scale-ups', 'gründer', 'startup', 'gründen', 'gründerin', 
                'entrepreneur', 'pitch', 'investor', 'funding', 'finanzierung', 
                'serie a', 'serie b', 'ipo', 'exit', 'acquisition', 'unicorn', 
                'disruption', 'geschäftsmodell', 'mvp', 'pivot', 'burn rate', 
                'runway', 'inkubator', 'accelerator'
            ],
            'high_priority': ['startup', 'gründer', 'venture capital', 'unicorn']
        },
        
        'BRAND_BRILLIANCE': {
            'name': 'Brand & Brilliance',
            'keywords': [
                'markenrevolution', 'digitale markenführung', 'content-strategie', 
                'disruptive kommunikation', 'digital branding', 'social media dominanz', 
                'influencer-marketing', 'brand storytelling', 'marketinginnovation',
                'marketing', 'marke', 'brand', 'werbung', 'kampagne', 'content', 
                'social media', 'influencer', 'instagram', 'tiktok', 'youtube', 
                'facebook', 'linkedin', 'twitter', 'storytelling', 'branding', 
                'logo', 'design', 'kommunikation', 'pr', 'public relations', 'seo'
            ],
            'high_priority': ['marketing', 'brand', 'influencer-marketing', 'content-strategie']
        },
        
        'BUSINESS_BEYOND': {
            'name': 'Business & Beyond',
            'keywords': [
                'wirtschaftsmacht deutschland', 'eu-dynamik', 'globale wirtschaftstrends', 
                'handelspolitik', 'mittelstandspolitik', 'standort europa', 
                'wirtschaftliche disruption', 'geopolitik', 'wirtschaftskrisen', 
                'internationale handelsbeziehungen', 'politik', 'wirtschaftspolitik', 
                'regierung', 'bundesregierung', 'bundestag', 'eu', 'europa', 
                'mittelstand', 'wirtschaft', 'handel', 'export', 'import', 'tarif', 
                'sanktion', 'inflation', 'rezession', 'zinsen', 'bundesbank', 'ezb', 
                'usa', 'china', 'globalisierung', 'wahlen', 'koalition'
            ],
            'high_priority': ['wirtschaftspolitik', 'eu', 'mittelstand', 'geopolitik']
        },
        
        # NEU: Finance & Freedom
        'FINANCE_FREEDOM': {
            'name': 'Finance & Freedom',
            'keywords': [
                'finanzielle unabhängigkeit', 'altersvorsorge', 'elternzeit', 'familienplanung', 
                'vermögensaufbau', 'smart money', 'investmentstrategie', 'finanz-hacks', 
                'krypto-welt', 'finanzfreiheit', 'börsenwissen', 'etfs', 'aktienmarkt', 
                'finanzplanung', 'investment', 'vermögensstrategien', 'finanzwissen', 
                'finanzen', 'lebensplanung', 'familie', 'rente', 'anlagepunk', 'aktien', 
                'börse', 'sparen', 'geld', 'euro', 'dollar', 'kryptowährung', 'bitcoin'
            ],
            'high_priority': ['finanzielle unabhängigkeit', 'vermögensaufbau', 'investment', 'krypto']
        },
        
        # NEU: Green & Generation
        'GREEN_GENERATION': {
            'name': 'Green & Generation',
            'keywords': [
                'klimaschutz', 'gesellschaftswandel', 'zukunftsmodelle', 'nachhaltige lebensweise', 
                'soziale innovation', 'green economy', 'kreislaufwirtschaft', 'zukunftsgenerationen', 
                'generationenübergreifendes denken', 'nachhaltigkeit', 'new life', 'gesellschaftlicher wandel', 
                'generationenübergreifende verantwortung', 'umwelt', 'klima', 'co2', 'erneuerbare energien', 
                'solar', 'wind', 'elektromobilität', 'bio', 'öko', 'fair trade', 'recycling'
            ],
            'high_priority': ['nachhaltigkeit', 'klimaschutz', 'green economy', 'zukunftsgenerationen']
        },
        
        # NEU: Female & Forward
        'FEMALE_FORWARD': {
            'name': 'Female & Forward',
            'keywords': [
                'female founders', 'gründerinnen', 'business-heldinnen', 'women in tech', 
                'leadership-queens', 'female investors', 'empowerment', 'diversity', 
                'equal pay', 'frauennetzwerke', 'female entrepreneurship', 'powerfrauen', 
                'diversity in business', 'frauen', 'weiblich', 'gender', 'gleichberechtigung', 
                'quote', 'ceo', 'chefin', 'unternehmerin', 'managerin', 'führungsfrau'
            ],
            'high_priority': ['female founders', 'gründerinnen', 'women in tech', 'empowerment']
        },
        
        # NEU: Deluxe & Destinations
        'DELUXE_DESTINATIONS': {
            'name': 'Deluxe & Destinations',
            'keywords': [
                'business-travel', 'workation', 'luxus-lifestyle', 'tech-gadgets', 
                'premium-experiences', 'digital nomads', 'high-end-destinationen', 
                'business-hotspots', 'smart living', 'geschäftsreisen', 'lifestyle', 
                'business-gadgets', 'premium-erlebnisse', 'luxus', 'reisen', 'hotel', 
                'first class', 'business class', 'premium', 'exklusiv', 'vip'
            ],
            'high_priority': ['business-travel', 'workation', 'luxus-lifestyle', 'premium-experiences']
        },
        
        # NEU: Drive & Dreams
        'DRIVE_DREAMS': {
            'name': 'Drive & Dreams',
            'keywords': [
                'mobilitätsrevolution', 'e-mobilität', 'automobilwende', 'elektrifizierung', 
                'autonomes fahren', 'mobilitätskonzepte', 'connected driving', 'tesla-effekt', 
                'urbane transportlösungen', 'fahrzeugdesign', 'automobilästhetik', 'traumfahrzeuge', 
                'automotive visionen', 'konzeptfahrzeuge', 'drivestyle', 'automotive disruption', 
                'mobilitätswende', 'traumautos', 'visionäre fahrzeugkonzepte', 'formschöne fahrzeuge', 
                'auto', 'elektroauto', 'tesla', 'bmw', 'mercedes', 'audi', 'porsche', 'ferrari'
            ],
            'high_priority': ['e-mobilität', 'autonomes fahren', 'tesla', 'elektroauto']
        }
    }
    
    # Zähle Keyword-Treffer pro Modul
    scores = {}
    
    for module_name, module_data in modules.items():
        score = 0
        
        # Normale Keywords (Gewicht: 1)
        for keyword in module_data['keywords']:
            matches = full_text.count(keyword)
            score += matches
        
        # Hochpriorisierte Keywords (Gewicht: 3)
        for priority_keyword in module_data.get('high_priority', []):
            matches = full_text.count(priority_keyword)
            score += matches * 3
        
        scores[module_name] = score
    
    # Bestimme das dominante Modul
    if max(scores.values()) == 0:
        return 'WORK_WINNING'  # Standard-Modul
    
    primary_module = max(scores, key=scores.get)
    
    # Debug-Ausgabe
    print(f"DEBUG: Modul-Scores: {scores}")
    print(f"DEBUG: Erkanntes Modul: {primary_module} ({modules[primary_module]['name']})")
    
    return primary_module

def get_module_info(module_key: str) -> dict:
    """
    Gibt detaillierte Informationen zu einem Modul zurück.
    ERWEITERT: Alle 10 Module aus Excel
    """
    modules_info = {
        'WORK_WINNING': {
            'name': 'Work & Winning',
            'description': 'Karrierewege, New Work, Arbeitsmodelle, Leadership, Zukunft der Arbeit',
            'url': '/work',
            'focus': 'Moderne Arbeitskonzepte und Karrierestrategien',
            'hashtags': ['#NewWork', '#FutureSkills', '#DigitalLeadership', '#RemoteWork', '#WorkLifeBalance']
        },
        'TECH_TRENDS': {
            'name': 'Tech & Trends',
            'description': 'NewMinds.AI, Digitalisierung, KI, Zukunftstechnologien',
            'url': '/tech',
            'focus': 'Disruptive Technologien und digitale Innovation',
            'hashtags': ['#KI', '#DigitalDisruption', '#TechRevolution', '#Innovation', '#Digitalisierung']
        },
        'STARTUP_SCALING': {
            'name': 'Startup & Scaling',
            'description': 'Gründerszene, Disruptive Innovationen, Entrepreneurship, Geschäftsmodelle',
            'url': '/startup',
            'focus': 'Gründertum und Unternehmenswachstum',
            'hashtags': ['#Startups', '#Gründerszene', '#VentureCapital', '#Scaling', '#Entrepreneurship']
        },
        'BRAND_BRILLIANCE': {
            'name': 'Brand & Brilliance',
            'description': 'Marketing-Revolutionen, Markenaufbau, Kommunikationsstrategien',
            'url': '/brand',
            'focus': 'Marketing-Innovation und Markenführung',
            'hashtags': ['#MarkenRevolution', '#DigitalBranding', '#ContentStrategy', '#InfluencerMarketing', '#BrandStorytelling']
        },
        'BUSINESS_BEYOND': {
            'name': 'Business & Beyond',
            'description': 'Deutsche, europäische und globale Wirtschaftspolitik, Mittelstand, internationale Märkte',
            'url': '/business',
            'focus': 'Wirtschaftspolitik und globale Märkte',
            'hashtags': ['#Wirtschaftspolitik', '#EUDynamik', '#Mittelstand', '#Geopolitik', '#WirtschaftsmachtDeutschland']
        },
        'FINANCE_FREEDOM': {
            'name': 'Finance & Freedom',
            'description': 'Investment, Vermögensstrategien, Finanzwissen, Finanzen, Lebensplanung, Familie, Rente',
            'url': '/finance',
            'focus': 'Finanzielle Unabhängigkeit und Vermögensaufbau',
            'hashtags': ['#FinanceFreedom', '#Vermögensaufbau', '#Investment', '#Finanzplanung', '#SmartMoney']
        },
        'GREEN_GENERATION': {
            'name': 'Green & Generation',
            'description': 'Nachhaltigkeit, New Life, Zukunftsmodelle, gesellschaftlicher Wandel, generationenübergreifende Verantwortung',
            'url': '/green',
            'focus': 'Nachhaltigkeit und Zukunftsverantwortung',
            'hashtags': ['#GreenGeneration', '#Nachhaltigkeit', '#Klimaschutz', '#GreenEconomy', '#Zukunftsgenerationen']
        },
        'FEMALE_FORWARD': {
            'name': 'Female & Forward',
            'description': 'Female Entrepreneurship, Powerfrauen, Diversity in Business',
            'url': '/female',
            'focus': 'Weibliches Unternehmertum und Diversity',
            'hashtags': ['#FemaleForward', '#FemaleFounders', '#WomenInBusiness', '#Diversity', '#Empowerment']
        },
        'DELUXE_DESTINATIONS': {
            'name': 'Deluxe & Destinations',
            'description': 'Geschäftsreisen, Lifestyle, Business-Gadgets, Premium-Erlebnisse',
            'url': '/deluxe',
            'focus': 'Premium-Lifestyle und Business-Travel',
            'hashtags': ['#DeluxeDestinations', '#BusinessTravel', '#Workation', '#LuxusLifestyle', '#PremiumExperiences']
        },
        'DRIVE_DREAMS': {
            'name': 'Drive & Dreams',
            'description': 'DriveStyle, E-Mobilität, Automotive Disruption, Mobilitätswende, Traumautos',
            'url': '/drive',
            'focus': 'Mobilität der Zukunft und Automotive Innovation',
            'hashtags': ['#DriveDreams', '#EMobility', '#FutureMobility', '#ElektroAuto', '#MobilitätsRevolution']
        }
    }
    
    return modules_info.get(module_key, modules_info['WORK_WINNING'])

def get_module_specific_instructions(module_key: str) -> str:
    """
    Gibt modulspezifische Anweisungen für die Artikel-Generierung zurück.
    ERWEITERT: Alle 10 Module aus Excel
    """
    instructions = {
        'WORK_WINNING': """
WORK & WINNING-FOKUS:
- Stelle moderne Arbeitskonzepte, Karrierestrategien oder New Work-Modelle in den Mittelpunkt
- Erkläre konkrete Auswirkungen auf Arbeitnehmer, Führungskräfte und Arbeitskultur
- Beleuchte innovative Führungsansätze, unkonventionelle Karrierewege oder Remote Work-Strategien
- Stelle Verbindungen zu Future Skills und digitaler Transformation der Arbeitswelt her
- Verwende ein Vokabular, das moderne Arbeitsweisen betont: "Future Skills", "New Work", "Digital Leadership"
- Nutze eine Tonalität, die zugleich karriereorientiert und zukunftsweisend ist
- Reality Check: Fokussiere auf echte Arbeitsmarkt-Realitäten vs. New Work-Hype
- FAQs: "Wie setze ich New Work-Konzepte um?", "Welche Future Skills brauche ich?", "Funktioniert Remote Leadership?"
""",
        
        'TECH_TRENDS': """
TECH & TRENDS-FOKUS:
- Stelle disruptive Technologien, KI-Innovationen oder digitale Transformation in den Mittelpunkt
- Erkläre die Funktionsweise und das Marktpotenzial neuartiger Tech-Lösungen
- Beleuchte die Auswirkungen auf bestehende Geschäftsmodelle und Branchen
- Zeige auf, wie Technologie ganze Industrien revolutioniert
- Verwende ein Vokabular, das technologischen Wandel betont: "Digital Disruption", "Tech-Revolution", "KI-Tools"
- Nutze eine Tonalität, die aufregend, tech-enthusiastisch und zukunftsorientiert ist
- Reality Check: Trenne Tech-Hype von echter Innovation und Praxistauglichkeit
- FAQs: "Welche KI-Tools sollten Unternehmen nutzen?", "Ist der Tech-Trend praxistauglich?", "Was kostet die Transformation?"
""",
        
        'STARTUP_SCALING': """
STARTUP & SCALING-FOKUS:
- Stelle Gründergeschichten, Startup-Strategien oder Scaling-Herausforderungen in den Mittelpunkt
- Erkläre innovative Geschäftsmodelle und Disruptions-Strategien
- Beleuchte Finanzierungsrunden, Venture Capital-Trends oder Unicorn-Entwicklungen
- Präsentiere konkrete Learnings aus erfolgreichen (und gescheiterten) Startups
- Verwende ein Vokabular, das Entrepreneurship betont: "Disruptor", "Scale-up", "Venture Capital", "Unicorn"
- Nutze eine Tonalität, die inspirierend, pragmatisch und gründerorientiert ist
- Reality Check: Entlarve Startup-Glamour und zeige echte Gründer-Realitäten
- FAQs: "Wie realistisch sind Unicorn-Träume?", "Welche Finanzierung braucht man?", "Was sind Scaling-Fehler?"
""",
        
        'BRAND_BRILLIANCE': """
BRAND & BRILLIANCE-FOKUS:
- Stelle Marketing-Innovationen, Brand-Strategien oder Content-Revolutionen in den Mittelpunkt
- Erkläre disruptive Kommunikationsansätze und moderne Markenführung
- Beleuchte erfolgreiche Kampagnen, Influencer-Strategien oder Social Media-Trends
- Präsentiere konkrete Marketing-ROI und messbare Brand-Performance
- Verwende ein Vokabular, das Marketing-Excellence betont: "Brand Storytelling", "Content-Strategie", "Digital Branding"
- Nutze eine Tonalität, die kreativ, strategisch und performance-orientiert ist
- Reality Check: Entlarve Marketing-Mythen und zeige echte Performance-Daten
- FAQs: "Funktioniert Influencer-Marketing noch?", "Wie messbar ist Content-Marketing ROI?", "Welche Brands sind Vorreiter?"
""",
        
        'BUSINESS_BEYOND': """
BUSINESS & BEYOND-FOKUS:
- Stelle Wirtschaftspolitik, geopolitische Entwicklungen oder Mittelstands-Themen in den Mittelpunkt
- Erkläre komplexe wirtschaftspolitische Zusammenhänge und deren Business-Auswirkungen
- Beleuchte EU-Politik, Handelskriege oder globale Wirtschaftstrends
- Präsentiere konkrete Auswirkungen auf deutsche Unternehmen und Märkte
- Verwende ein Vokabular, das Wirtschaftsmacht betont: "EU-Dynamik", "Handelspolitik", "Geopolitik"
- Nutze eine Tonalität, die analytisch, kritisch und business-relevant ist
- Reality Check: Durchbreche politische Phrasen und zeige echte Business-Konsequenzen
- FAQs: "Wie wirkt sich EU-Politik auf Startups aus?", "Was bedeutet das für den Mittelstand?", "Welche Branchen profitieren?"
""",

        # NEU: Die 5 zusätzlichen Module
        'FINANCE_FREEDOM': """
FINANCE & FREEDOM-FOKUS:
- Stelle finanzielle Unabhängigkeit, Investment-Strategien oder Vermögensaufbau in den Mittelpunkt
- Erkläre moderne Anlageformen, Fintech-Innovationen oder Krypto-Entwicklungen
- Beleuchte persönliche Finanzplanung, Altersvorsorge oder Family Finance-Strategien
- Präsentiere konkrete Finanz-Tools und messbare Investment-Performance
- Verwende ein Vokabular, das Finanz-Expertise betont: "Smart Money", "Finanz-Hacks", "Vermögensaufbau"
- Nutze eine Tonalität, die pragmatisch, bildend und erfolgsorientiiert ist
- Reality Check: Entlarve Finanz-Mythen und zeige echte Rendite-Realitäten
- FAQs: "Welche Anlagestrategien funktionieren?", "Wie realistisch ist Finanzfreiheit?", "Was kostet professionelle Finanzplanung?"
""",

        'GREEN_GENERATION': """
GREEN & GENERATION-FOKUS:
- Stelle Nachhaltigkeits-Innovationen, Klimaschutz-Strategien oder Green Business in den Mittelpunkt
- Erkläre nachhaltige Geschäftsmodelle, Circular Economy oder ESG-Strategien
- Beleuchte generationenübergreifende Verantwortung und Zukunftsmodelle
- Präsentiere konkrete Klima-Lösungen und messbare Nachhaltigkeits-Impact
- Verwende ein Vokabular, das Zukunftsverantwortung betont: "Green Economy", "Klimaschutz", "Zukunftsgenerationen"
- Nutze eine Tonalität, die verantwortungsbewusst, zukunftsorientiert und handlungsorientiert ist
- Reality Check: Entlarve Greenwashing und zeige echte Nachhaltigkeits-Realitäten
- FAQs: "Wie nachhaltig sind grüne Investments?", "Was bringt Corporate Sustainability?", "Welche Klima-Technologien haben Zukunft?"
""",

        'FEMALE_FORWARD': """
FEMALE & FORWARD-FOKUS:
- Stelle erfolgreiche Gründerinnen, Female Leadership oder Diversity-Innovationen in den Mittelpunkt
- Erkläre weibliche Erfolgsstrategien, Netzwerk-Power oder Gender-Equality-Fortschritte
- Beleuchte Female Entrepreneurship, Women in Tech oder Business-Heldinnen
- Präsentiere konkrete Diversity-Erfolge und messbare Equality-Fortschritte
- Verwende ein Vokabular, das Female Power betont: "Female Founders", "Leadership-Queens", "Empowerment"
- Nutze eine Tonalität, die inspirierend, empowernd und gleichzeitig business-fokussiert ist
- Reality Check: Entlarve Gender-Mythen und zeige echte Diversity-Realitäten
- FAQs: "Welche Chancen haben Gründerinnen?", "Wie funktioniert Female Networking?", "Was bringt Diversity im Business?"
""",

        'DELUXE_DESTINATIONS': """
DELUXE & DESTINATIONS-FOKUS:
- Stelle Premium-Erlebnisse, Business-Travel-Trends oder Luxury-Lifestyle in den Mittelpunkt
- Erkläre exklusive Destinationen, High-End-Experiences oder Smart Living-Konzepte
- Beleuchte Workation-Strategien, Digital Nomad-Lifestyle oder Business-Hotspots
- Präsentiere konkrete Premium-Services und messbare Lifestyle-Benefits
- Verwende ein Vokabular, das Exklusivität betont: "Premium-Experiences", "Business-Travel", "Luxus-Lifestyle"
- Nutze eine Tonalität, die aspirational, sophisticated und gleichzeitig business-relevant ist
- Reality Check: Entlarve Luxury-Mythen und zeige echte Premium-Realitäten
- FAQs: "Welche Business-Travel-Trends kommen?", "Wie funktioniert erfolgreiches Workation?", "Was kostet Premium-Lifestyle?"
""",

        'DRIVE_DREAMS': """
DRIVE & DREAMS-FOKUS:
- Stelle Mobilitäts-Innovationen, E-Mobilität oder Automotive-Disruption in den Mittelpunkt
- Erkläre autonomes Fahren, Connected Driving oder urbane Transportlösungen
- Beleuchte Tesla-Effekt, Elektrifizierung oder visionäre Fahrzeugkonzepte
- Präsentiere konkrete Mobility-Trends und messbare Automotive-Performance
- Verwende ein Vokabular, das Mobilitäts-Revolution betont: "E-Mobilität", "Autonomes Fahren", "Mobilitätswende"
- Nutze eine Tonalität, die tech-enthusiastisch, zukunftsorientiert und performance-fokussiert ist
- Reality Check: Entlarve Mobility-Mythen und zeige echte Automotive-Realitäten
- FAQs: "Welche E-Autos haben Zukunft?", "Wie realistisch ist autonomes Fahren?", "Was kostet die Mobilitätswende?"
"""
    }
    
    return instructions.get(module_key, instructions['WORK_WINNING'])

def get_reality_check_focus(module_key: str) -> str:
    """
    Gibt modulspezifische Business Punk Check-Fokussierung zurück.
    ERWEITERT: Alle 10 Module aus Excel
    """
    reality_focus = {
        'WORK_WINNING': 'Fokussiere auf echte Arbeitsmarkt-Realitäten vs. New Work-Hype. Entlarve Remote Work-Mythen und zeige konkrete Karriere-Auswirkungen.',
        'TECH_TRENDS': 'Trenne Tech-Hype von echter Innovation. Entlarve KI-Marketing und zeige echte Praxistauglichkeit von Technologien.',
        'STARTUP_SCALING': 'Entlarve Startup-Glamour und Unicorn-Mythen. Zeige echte Gründer-Realitäten jenseits der Erfolgsgeschichten.',
        'BRAND_BRILLIANCE': 'Entlarve Marketing-Mythen und Influencer-Hype. Zeige echte Performance-Daten statt Vanity Metrics.',
        'BUSINESS_BEYOND': 'Durchbreche politische Phrasen und Wirtschafts-Buzzwords. Zeige echte Business-Konsequenzen politischer Entscheidungen.',
        
        # NEU: Die 5 zusätzlichen Module
        'FINANCE_FREEDOM': 'Entlarve Finanz-Mythen und Get-Rich-Quick-Versprechen. Zeige echte Rendite-Realitäten und Investment-Risiken.',
        'GREEN_GENERATION': 'Entlarve Greenwashing und Nachhaltigkeits-Marketing. Zeige echte Klima-Impact und reale Kosten grüner Transformation.',
        'FEMALE_FORWARD': 'Entlarve Gender-Klischees und Diversity-Tokenismus. Zeige echte Gleichstellungs-Fortschritte und strukturelle Barrieren.',
        'DELUXE_DESTINATIONS': 'Entlarve Luxury-Marketing und Premium-Versprechen. Zeige echte Kosten-Nutzen-Realitäten von Lifestyle-Investments.',
        'DRIVE_DREAMS': 'Entlarve Mobility-Hype und E-Auto-Versprechen. Zeige echte Reichweiten-Realitäten und Infrastruktur-Herausforderungen.'
    }
    
    return reality_focus.get(module_key, reality_focus['WORK_WINNING'])

def get_faq_angles(module_key: str) -> str:
    """
    Gibt modulspezifische FAQ-Winkel zurück (für Business Punk Check).
    ERWEITERT: Alle 10 Module aus Excel
    """
    faq_angles = {
        'WORK_WINNING': 'Umsetzung von New Work-Konzepten, Future Skills-Bedarf, Remote Leadership-Realitäten, Karriere-Auswirkungen',
        'TECH_TRENDS': 'Praxistauglichkeit von KI-Tools, Technologie-Investitionen, Disruptions-Wahrscheinlichkeit, Implementierungskosten',
        'STARTUP_SCALING': 'Erfolgsaussichten, Finanzierungsbedarf, Scaling-Herausforderungen, Risiko-Bewertung',
        'BRAND_BRILLIANCE': 'Marketing-ROI, Performance-Messung, Tool-Effizienz, Strategie-Nachhaltigkeit',
        'BUSINESS_BEYOND': 'Unternehmens-Auswirkungen, Mittelstands-Konsequenzen, Branchen-Effekte, Vorbereitung auf Veränderungen',
        
        # NEU: Die 5 zusätzlichen Module
        'FINANCE_FREEDOM': 'Investment-Strategien, Rendite-Realismus, Finanzplan-Umsetzung, Risiko-Management',
        'GREEN_GENERATION': 'Nachhaltigkeits-ROI, Klima-Impact-Messung, Green-Business-Chancen, ESG-Implementierung',
        'FEMALE_FORWARD': 'Gründerinnen-Chancen, Female Networking-Strategien, Diversity-Business-Case, Equality-Fortschritte',
        'DELUXE_DESTINATIONS': 'Premium-ROI, Lifestyle-Investment-Bewertung, Business-Travel-Effizienz, Luxury-Kosten-Nutzen',
        'DRIVE_DREAMS': 'E-Mobilität-Praxistauglichkeit, Automotive-Investment-Chancen, Mobility-Kosten, Infrastruktur-Realitäten'
    }
    
    return faq_angles.get(module_key, faq_angles['WORK_WINNING'])

def get_social_media_hashtags(module_key: str, platform: str = 'linkedin') -> list:
    """
    Gibt modulspezifische Hashtags für Social Media zurück.
    ERWEITERT: Alle 10 Module
    """
    hashtag_mapping = {
        'WORK_WINNING': {
            'linkedin': ['#BusinessPunk', '#NewWork', '#FutureSkills', '#DigitalLeadership', '#RemoteWork', '#WorkLifeBalance'],
            'facebook': ['#BusinessPunk', '#NewWork', '#Karriere', '#Leadership', '#RemoteWork']
        },
        'TECH_TRENDS': {
            'linkedin': ['#BusinessPunk', '#KI', '#DigitalDisruption', '#TechRevolution', '#Innovation', '#Digitalisierung'],
            'facebook': ['#BusinessPunk', '#KI', '#Innovation', '#TechTrends', '#Digitalisierung']
        },
        'STARTUP_SCALING': {
            'linkedin': ['#BusinessPunk', '#Startups', '#Gründerszene', '#VentureCapital', '#Scaling', '#Entrepreneurship'],
            'facebook': ['#BusinessPunk', '#Startups', '#Gründer', '#Innovation', '#Entrepreneurship']
        },
        'BRAND_BRILLIANCE': {
            'linkedin': ['#BusinessPunk', '#MarkenRevolution', '#DigitalBranding', '#ContentStrategy', '#InfluencerMarketing', '#BrandStorytelling'],
            'facebook': ['#BusinessPunk', '#Marketing', '#Branding', '#ContentStrategy', '#InfluencerMarketing']
        },
        'BUSINESS_BEYOND': {
            'linkedin': ['#BusinessPunk', '#Wirtschaftspolitik', '#EUDynamik', '#Mittelstand', '#Geopolitik', '#WirtschaftsmachtDeutschland'],
            'facebook': ['#BusinessPunk', '#Wirtschaftspolitik', '#Politik', '#Mittelstand', '#Europa']
        },
        'FINANCE_FREEDOM': {
            'linkedin': ['#BusinessPunk', '#FinanceFreedom', '#Vermögensaufbau', '#Investment', '#Finanzplanung', '#SmartMoney'],
            'facebook': ['#BusinessPunk', '#Finanzen', '#Investment', '#Vermögensaufbau', '#Finanzfreiheit']
        },
        'GREEN_GENERATION': {
            'linkedin': ['#BusinessPunk', '#GreenGeneration', '#Nachhaltigkeit', '#Klimaschutz', '#GreenEconomy', '#Zukunftsgenerationen'],
            'facebook': ['#BusinessPunk', '#Nachhaltigkeit', '#Klimaschutz', '#GreenBusiness', '#Zukunft']
        },
        'FEMALE_FORWARD': {
            'linkedin': ['#BusinessPunk', '#FemaleForward', '#FemaleFounders', '#WomenInBusiness', '#Diversity', '#Empowerment'],
            'facebook': ['#BusinessPunk', '#FemaleFounders', '#WomenInBusiness', '#Diversity', '#Frauen']
        },
        'DELUXE_DESTINATIONS': {
            'linkedin': ['#BusinessPunk', '#DeluxeDestinations', '#BusinessTravel', '#Workation', '#LuxusLifestyle', '#PremiumExperiences'],
            'facebook': ['#BusinessPunk', '#BusinessTravel', '#Workation', '#Luxus', '#Premium']
        },
        'DRIVE_DREAMS': {
            'linkedin': ['#BusinessPunk', '#DriveDreams', '#EMobility', '#FutureMobility', '#ElektroAuto', '#MobilitätsRevolution'],
            'facebook': ['#BusinessPunk', '#EMobility', '#ElektroAuto', '#Tesla', '#Mobilität']
        }
    }
    
    return hashtag_mapping.get(module_key, {}).get(platform, hashtag_mapping['WORK_WINNING'][platform])

def get_module_specific_social_guidance(module_key: str) -> str:
    """
    Gibt modulspezifische Social Media-Anweisungen zurück.
    ERWEITERT: Alle 10 Module aus Excel
    """
    guidance = {
        'WORK_WINNING': 'Betone Karriere-Auswirkungen und New Work-Realitäten. Richte Call-to-Action an zukunftsorientierte Professionals.',
        'TECH_TRENDS': 'Betone disruptive Aspekte und Technologie-Durchbrüche. Richte Call-to-Action an Innovatoren und Tech-Enthusiasten.',
        'STARTUP_SCALING': 'Betone Gründer-Realitäten und Scaling-Insights. Richte Call-to-Action an Entrepreneurs und Investoren.',
        'BRAND_BRILLIANCE': 'Betone Marketing-Performance und Brand-Innovationen. Richte Call-to-Action an Marketing-Professionals.',
        'BUSINESS_BEYOND': 'Betone wirtschaftspolitische Auswirkungen. Richte Call-to-Action an Business-Entscheider und Mittelständler.',
        
        # NEU: Die 5 zusätzlichen Module
        'FINANCE_FREEDOM': 'Betone finanzielle Chancen und Investment-Strategien. Richte Call-to-Action an finanzaffine Professionals und angehende Investoren.',
        'GREEN_GENERATION': 'Betone Nachhaltigkeits-Chancen und Zukunftsverantwortung. Richte Call-to-Action an nachhaltigkeitsorientierte Unternehmer und Klimabewusste.',
        'FEMALE_FORWARD': 'Betone weibliche Erfolgsgeschichten und Diversity-Fortschritte. Richte Call-to-Action an Gründerinnen und Diversity-Champions.',
        'DELUXE_DESTINATIONS': 'Betone Premium-Erlebnisse und Business-Travel-Trends. Richte Call-to-Action an erfolgreiche Professionals und Lifestyle-Enthusiasten.',
        'DRIVE_DREAMS': 'Betone Mobilitäts-Innovationen und Automotive-Trends. Richte Call-to-Action an technikaffine Mobilitätsnutzer und Auto-Enthusiasten.'
    }
    
    return guidance.get(module_key, guidance['WORK_WINNING'])

# =============================================================================
# ENDE DER NEUEN FUNKTIONEN
# =============================================================================

def process_text_for_seo(article_text: str, source_info: str = "", custom_instructions: str = "", word_count: str = "650") -> str:
    """
    Generate SEO-optimized article with built-in source validation to prevent hallucinations.
    UPDATED: Mit neuen Business Punk Modulen und Reality Check
    """
    
    # SCHRITT 1: Automatische Modul-Erkennung (NEU!)
    primary_module = analyze_theme_module(article_text, source_info)
    module_info = get_module_info(primary_module)
    module_instructions = get_module_specific_instructions(primary_module)
    
    print(f"🎯 Erkanntes Modul: {module_info['name']} ({primary_module})")
    print(f"📊 Fokus: {module_info['focus']}")
    
    # SCHRITT 2: Extrahiere echte Zitate und Fakten aus dem Quellentext (BLEIBT GLEICH)
    def extract_real_quotes_from_source(text):
        """Extrahiert echte Zitate direkt aus dem Quellentext"""
        import re
        quotes = []
        
        # Verschiedene Anführungszeichen-Patterns
        patterns = [
            r'"([^"]{15,200})"',  # Normale Anführungszeichen
            r'„([^"]{15,200})"',  # Deutsche Anführungszeichen  
            r'»([^«]{15,200})«',  # Guillemets
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Filtere Titel und Headers raus
                if not any(x in match for x in ['|', ':', 'Breaking', 'News', 'ECHO']):
                    quotes.append(match.strip())
        
        return list(set(quotes))[:5]  # Max 5 echte Zitate
    
    def extract_concrete_facts(text):
        """Extrahiert konkrete Fakten und Zahlen aus dem Quellentext"""
        import re
        facts = []
        
        # Zahlen und Fakten Patterns
        patterns = [
            r'\d+(?:\.\d+)?\s*(?:Prozent|%|Euro|€|Dollar|\$|Millionen|Milliarden|Mio\.|Mrd\.)',  # Zahlen mit Einheiten
            r'(?:um|auf|bei|von|bis)\s+\d+(?:\.\d+)?\s*(?:Prozent|%|Euro|€|Dollar|\$)',  # Zahlen in Kontext
            r'\d{4}',  # Jahreszahlen
            r'(?:seit|vor|nach)\s+\d{1,2}\.\s*\d{1,2}\.\s*\d{4}',  # Datumsangaben
            r'(?:am|bis|ab)\s+\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)',  # Monatsangaben
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) > 5:  # Nur relevante Fakten
                    facts.append(match.strip())
        
        # Entferne Duplikate und sortiere nach Länge
        facts = list(set(facts))
        facts.sort(key=len, reverse=True)
        
        return facts[:10]  # Max 10 konkrete Fakten
    
    def extract_sources_from_info(source_info):
        """
        KORRIGIERT: Extrahiert saubere Quellennamen für kursive Formatierung
        Format: "Spiegel", "n-tv", "Süddeutsche Zeitung"
        """
        import re
        sources = []

        print(f"DEBUG: Verarbeite source_info: {source_info[:500]}...")
        
        # Suche nach dem Pattern "Quelle X: Beschreibung (domain)"
        pattern = r'Quelle\s+\d+:\s+([^(]+)\s*\(([^)]+)\)'
        matches = re.findall(pattern, source_info)
        
        print(f"DEBUG: Gefundene Matches: {matches}")
        
        for description, domain in matches:
            # Extrahiere sauberen Quellennamen aus der Beschreibung
            if "Nachrichtensender" in description or "n-tv" in description.lower():
                sources.append("n-tv")
            elif "Nachrichtenmagazin Spiegel" in description or "spiegel" in description.lower():
                sources.append("Spiegel")
            elif "Süddeutsche Zeitung" in description:
                sources.append("Süddeutsche Zeitung")
            elif "Zeit" in description and "Wochenzeitung" in description:
                sources.append("Zeit")
            elif "Handelsblatt" in description:
                sources.append("Handelsblatt")
            elif "Bild" in description:
                sources.append("Bild")
            elif "Business Insider" in description:
                sources.append("Business Insider")
            elif "Manager Magazin" in description:
                sources.append("Manager Magazin")
            elif "Frankfurter Allgemeine" in description:
                sources.append("FAZ")
            elif "TechCrunch" in description:
                sources.append("TechCrunch")
            elif "Gründerszene" in description:
                sources.append("Gründerszene")
            else:
                # Fallback: Versuche Domain-Namen zu bereinigen
                clean_domain = domain.replace('www.', '').replace('.de', '').replace('.com', '')
                
                if clean_domain == "n-tv":
                    sources.append("n-tv")
                elif clean_domain == "spiegel":
                    sources.append("Spiegel")
                elif clean_domain == "sueddeutsche":
                    sources.append("Süddeutsche Zeitung")
                elif clean_domain == "zeit":
                    sources.append("Zeit")
                else:
                    sources.append(clean_domain.capitalize())
        
        # Fallback: Falls keine Matches gefunden
        if not sources:
            print("DEBUG: Fallback - suche nach Domains")
            domain_pattern = r'([a-zA-Z0-9-]+\.(?:de|com|net|org))'
            domain_matches = re.findall(domain_pattern, source_info)
            for domain in domain_matches:
                base_name = domain.split('.')[0]
                if base_name == "n-tv":
                    sources.append("n-tv")
                elif base_name == "spiegel":
                    sources.append("Spiegel")
                elif base_name == "sueddeutsche":
                    sources.append("Süddeutsche Zeitung")
                else:
                    sources.append(base_name.capitalize())
        
        print(f"DEBUG: Finale Quellen: {sources}")
        return sources

    
    # SCHRITT 3: Analysiere verfügbare Quellen und Inhalte (BLEIBT GLEICH)
    real_quotes = extract_real_quotes_from_source(article_text)
    concrete_facts = extract_concrete_facts(article_text)
    available_sources = extract_sources_from_info(source_info)
    
    # SCHRITT 4: Erstelle den erweiterten Prompt mit neuen Modulen (GEÄNDERT!)
    base_prompt = f"""KRITISCHE ANTI-HALLYZINATIONS-REGELN - STRIKT BEFOLGEN:

1. QUELLEN UND ZITATE:
    - Verfügbare Quellen: {', '.join(available_sources) if available_sources else 'Nutze die Quellen aus der Quellenliste'}

   WICHTIG FÜR QUELLENANGABEN:
    - ALLE Quellennamen im Text IMMER in Anführungszeichen: "Spiegel", "Bild", "Zeit", "Business Insider"
    - NIEMALS ohne Anführungszeichen: laut Spiegel ❌
    - IMMER mit Anführungszeichen: laut "Spiegel" ✅
    - NIEMALS klein schreiben: laut "bild" ❌
    - IMMER korrekt kapitalisiert: laut "Bild" ✅
    - FORMAT: "laut 'Quellenname'", so "Quellenname" berichtet, wie "Quellenname" meldet
    - BEISPIELE: laut "Spiegel", so "Handelsblatt", wie "Business Insider" berichtet

   WICHTIG GEGEN ZEILENUMBRUCH-PROBLEME:
    - Quellenangaben kompakt halten: "laut Spiegel" statt "laut dem Nachrichtenmagazin Spiegel"
    - Kurze Quellennamen bevorzugen: "Spiegel" statt "Spiegel Online"
    - Quellenangaben am Satzanfang oder -mitte platzieren, nicht am Ende langer Sätze
    - Beispiele: "Spiegel berichtet, dass..." statt "...berichtet Spiegel."
    - Vermeide: "...erklärt das Management laut Spiegel." (zu lang)
    - Besser: "Laut Spiegel erklärt das Management..." (kompakter)
    
   ZITATE (mit Anführungszeichen):
    - ABSOLUT KRITISCH: JEDES Zitat SOFORT mit Quelle
    - Format: „Zitat hier", so "Quellenname"
    - NIEMALS: „Zitat", kommentiert Person (ohne Quelle)
    - IMMER: „Zitat", so Person laut "Quellenname"
    - WORTGETREUE ÜBERNAHME: Zitate müssen EXAKT übernommen werden

    SEKUNDÄRQUELLEN-REGEL:
    - Wenn eine Quelle eine andere Quelle zitiert: Nenne die URSPRUNGSQUELLE
    - Format: wie "BILD" berichtet (auch wenn über Merkur verfügbar)
    - Transparente Alternative: "merkur" unter Berufung auf "BILD"
    - NICHT: "laut merkur" (wenn merkur BILD zitiert)
    - Beispiel: Merkur zitiert BILD → verwende "so BILD"
   
   FAKTEN-QUELLENANGABEN (1x pro Absatz):
    - EXTREM WICHTIG mindestens eine strategische Quellenangabe pro Absatz
    - WANN: Bei wichtigen Zahlen, kontroversen Aussagen, spezifischen Fakten
    - WO: Meist im mittleren Satz des Absatzes
    - FORMAT: "laut Quellenname", so "Quellenname" berichtet, wie "Quellenname" meldet

   🚨 ANFÜHRUNGSZEICHEN-VERBOT 🚨
    - NIEMALS Anführungszeichen um Inhalte setzen, die im Original keine haben
    - Indirekte Rede bleibt OHNE Anführungszeichen  
    - NUR echte Direktzitate aus den Quellen in Anführungszeichen

2. QUELLENVERTEILUNG:
    - Verfügbare Quellen: {', '.join(available_sources) if available_sources else 'Business Insider, Berliner Zeitung'}
    - ALLE Quellennamen in Anführungszeichen: "Business Insider", "Berliner Zeitung"
    - Variation: "laut", "so", "berichtet", "erklärt", "meldet", "dokumentiert"
    - Balance: Wichtige Fakten MIT Quelle, Allgemeinwissen OHNE Quelle

VERFÜGBARE ECHTE ZITATE AUS DEM ORIGINALTEXT:
{chr(10).join([f'• "{quote}"' for quote in real_quotes[:5]]) if real_quotes else '• Keine direkten Zitate im Originaltext gefunden - verwende nur indirekte Rede'}

WICHTIGE ZITAT-VERWENDUNGSREGELN:
- Verwende die oben aufgelisteten echten Zitate WÖRTLICH (keine Änderungen!)
- Jedes verwendete Zitat MUSS mit der korrekten Quelle versehen werden
- Format: „Zitat hier", so "Quellenname" 
- Falls keine echten Zitate verfügbar: NUR indirekte Rede im Konjunktiv I verwenden
- NIEMALS eigene Zitate erfinden - nur die oben gelisteten verwenden!

VERFÜGBARE KONKRETE FAKTEN:
{chr(10).join([f'• {fact[:100]}...' for fact in concrete_facts[:5]]) if concrete_facts else '• Nutze nur Fakten aus dem bereitgestellten Originaltext'}

🎯 ERKANNTES THEMENMODUL: {primary_module} ({module_info['name']})
📊 MODULARER FOKUS: {module_info['focus']}

{module_instructions}

Hier sind die Quellen für einen Business Punk Artikelentwurf:

{source_info}

QUELLENTEXT:
{article_text}

🚨 KRITISCHE ERINNERUNG 🚨
- JEDES Zitat braucht SOFORT eine Quellenangabe
- Pro Absatz EINE strategische Quellenangabe bei wichtigen Fakten
- Qualität vor Quantität bei Quellenangaben

Erstelle einen SEO-optimierten, journalistischen Artikel auf dem vorliegenden Entwurf.

Du bist ein erfahrener Wirtschafts- und Lifestyle-Journalist mit tiefem Verständnis für moderne Business-Themen wie Startups, digitale Transformation, Leadership, Nachhaltigkeit und innovative Geschäftsmodelle. Deine Aufgabe ist es, prägnante, faktenbasierte und informative Artikel in deutscher Sprache zu verfassen, die den charakteristischen Business Punk-Stil widerspiegeln: selbstbewusst, progressiv und auf den Punkt. Die Texte sollten eine klare Struktur aufweisen und die wichtigsten Ereignisse sowie Schlüsselmomente des Artikelentwurfs hervorheben. 

# Umfang und Inhalt
- Der Artikel soll prägnant und fokussiert sein (maximal {word_count} Wörter)
- Behalte alle wichtigen Fakten, Daten und Kernaussagen des Originaltextes bei
- Formuliere KOMPLETT NEU: Sätze, Absätze, Strukturen und Ausdrucksweisen müssen völlig anders sein als im Original
- Konzentriere dich auf innovative und zukunftsweisende Aspekte des Themas
    
# Stil und Tonalität
- Schreibe im charakteristischen Business Punk-Stil: progressiv, intelligent und selbstbewusst
- Richte dich an eine junge, digital-affine Zielgruppe (25-40 Jahre), die an Innovation und neuen Business-Modellen interessiert ist
- Verwende einen modernen, urbanen Sprachstil mit SEHR SPARSAMER Verwendung von Anglizismen (maximal 3-4 im gesamten Text)
- Sprich die Leser indirekt an (nie mit "Du" oder "Sie")
- Integriere gelegentlich provokante oder überraschende Elemente, ohne übertrieben frech zu wirken
- Verwende vorwiegend klare, direkte Sätze und vermeide komplizierte Satzkonstruktionen
- Nutze punktuell starke Adjektive wie "disruptiv", wenn sie zum Thema passen, aber ohne sie zu überstrapazieren"""

    # Add custom instructions if provided
    if custom_instructions.strip():
        base_prompt += f"\n\nWICHTIG: Zusätzliche spezifische Anweisungen für diesen Artikel:\n{custom_instructions}"

    # SCHRITT 5: Vervollständige den Prompt mit Struktur-Anforderungen (GEÄNDERT: Reality Check!)
    complete_prompt = base_prompt + f"""

Der Artikel muss folgende Elemente enthalten:

ANTI-KI-FLOSKELN REGELN - BUSINESS PUNK AUTHENTIZITÄT:
- VERMEIDE typische KI-Phrasen: "Die Zahlen sind beeindruckend", "zeigt exemplarisch", "sprechen Bände"
- VERMEIDE Drama-Floskeln: "entfachte den Zorn", "fundamentale Zäsur", "Doch damit nicht genug"
- VERMEIDE Business-Buzzwords: "disruptiv", "Game-Changer", "paradigmenwechsel" 
- NUTZE stattdessen: direkte, natürliche Formulierungen wie ein erfahrener Wirtschaftsjournalist
- SCHREIBE authentisch und frech, aber nicht überdramatisch
- VERMEIDE roboterhafte Übergänge wie "Besonders bemerkenswert", "Was unterscheidet X wirklich"
- BEVORZUGE natürliche Verbindungen: "Außerdem", "Dabei", "Zusätzlich", "Parallel dazu"

## **Titel**
Entwickle einen KURZEN, FRECHEN und CATCHY Titel (max. 60 Zeichen), der:
- Sofort Aufmerksamkeit erregt und mit Konventionen bricht
- Einen überraschenden oder relevanten Aspekt des Themas hervorhebt
- Relevante Keywords enthält (ohne übertriebenes Keyword-Stuffing)
- Den Business Punk-Stil verkörpert: frech, überraschend, direkt
- Verwende aktive Verben, überraschende Wendungen oder leicht provokante Formulierungen
- SEHR WICHTIG: Halte den Titel KURZ und PRÄGNANT - weniger ist mehr!

## **Abstract**
Erstelle ein prägnantes Abstract (max. 230 Zeichen), das:
- Die Kernaussage des Artikels pointiert zusammenfasst
- Die wichtigsten Keywords enthält
- Einen "Hook" setzt, der Lesermotivation schafft

## **Artikelbody**
Schreibe einen prägnanten und fokussierten Artikel (maximal {word_count} Wörter) mit genau dieser Struktur:

1. Einleitungsabsatz ohne Überschrift: 
- Beginne mit einem unerwarteten Fakt, einer pointierten These oder einem klaren Statement
- Stelle das Thema vor und verdeutliche dessen Relevanz
- Vermittle in 2-3 prägnanten Sätzen, warum das Thema gerade jetzt wichtig ist
- Nutze eine direkte, präzise Sprache mit hoher Informationsdichte
- EXTREM WICHTIG: Dieser erste Abschnitt hat keine Überschrift und steht direkt nach dem Abstract!
- Der Einleitungsabsatz steht ALLEINE und OHNE Überschrift am Anfang des Artikels!

2. Dann erst folgen die Hauptteil-Abschnitte mit Überschriften:
- ERST NACH dem ersten Einleitungsabsatz beginnen die Überschriften
- Jede Überschrift verwendet genau das Format "## Überschrift" (H2)
- NIEMALS eine Überschrift vor dem ersten Absatz setzen!

Der Artikelinhalt soll je nach erkanntem Themenmodul ({primary_module}) folgende spezifische Elemente enthalten:

{module_instructions}

3. Business Punk Check (ERSETZT DEN ALTEN AUSBLICK!):
- Liefere einen schonungslosen Business Punk Check (ca. 120-150 Wörter)
- Durchbreche Hype und Oberflächlichkeit mit harten Fakten
- Benenne sowohl Potenziale als auch realistische Stolpersteine
- Verwende einen entlarvenden, aber konstruktiven Ton
- Stelle eine provokante These auf, die zum Umdenken zwingt
- Beantworte: "Was bedeutet das WIRKLICH für Entscheider?"
- Vermeide Standard-Phrasen und Consultant-Speak
- Formuliere konkrete Handlungsempfehlungen für Early Adopters
- MODULSPEZIFISCH: {get_reality_check_focus(primary_module)}

## **Metabeschreibung**
Erstelle eine prägnante Metabeschreibung (150-160 Zeichen), die:
- Die Kernaussage des Artikels zusammenfasst
- Die wichtigsten Keywords enthält
- Einen Anreiz zum Klicken bietet
- SEO-Best-Practices folgt (klare Aussage, Call-to-Action, relevante Keywords)
    
## **Keywords**
Generiere 5-10 SEO-relevante Keywords:
- Primäre Keywords (1-2): Die Hauptthemen des Artikels
- Sekundäre Keywords (2-3): Wichtige Teilaspekte
- Long-Tail Keywords (2-5): Spezifischere Suchanfragen
- Verwende modulspezifische Keywords: {', '.join(module_info['hashtags'][:3])}
- Gib die Liste als kommagetrennte Zeichenkette aus

## **Häufig gestellte Fragen**
Erstelle 4-5 häufig gestellte Fragen die DIREKT auf den Reality Check aufbauen:
- Nutze die Reality Check-Erkenntnisse als FAQ-Grundlage
- Jede FAQ sollte eine konkrete Handlungsanweisung enthalten
- Integriere SEO-Keywords aus dem {primary_module}-Bereich
- Business Punk-Stil: direkt, lösungsorientiert, ohne Bullshit
- MODULSPEZIFISCHE FAQ-WINKEL: {get_faq_angles(primary_module)}

FORMAT für die FAQs:
**Frage 1: [Reality Check-basierte Frage zum Hauptthema]**
[Prägnante Antwort die auf Reality Check-Erkenntnissen aufbaut]

**Frage 2: [Praktische Umsetzungsfrage basierend auf Reality Check]**
[Konkrete Handlungsanweisung mit Business Punk-Attitude]

**Frage 3: [Zukunfts-/Trend-orientierte Frage aus Reality Check abgeleitet]**
[Zukunftsorientierte Antwort mit klarer Einschätzung]

[Optional: Frage 4 & 5 für komplexere Themen]

KRITISCH: FAQs müssen eine logische Fortsetzung des Reality Checks sein!

## **Reality Check**
Erstelle einen schonungslosen Reality Check, der:
- Hype von Realität trennt mit konkreten Beispielen
- {get_reality_check_focus(primary_module)}
- Eine provokante These für die FAQ-Generierung aufstellt
- Konkrete Handlungsoptionen für die {module_info['name']}-Zielgruppe zeigt

## **Quellen**
WICHTIG: Verwende EXAKT das Format aus der Quelleninfo:
- Wenn "QUELLEN FÜR ARTIKEL:" in der Quelleninfo steht, nutze das Format
- Schreibe: QUELLEN FÜR ARTIKEL:\n"Quelle1", "Quelle2", "Quelle3"
- NICHT: ## **Quellen** oder andere Formatierungen

Beachte:
- WICHTIG: Der Artikelbody muss mit genau der Überschrift "## **Artikelbody**" beginnen und wird bis zur Überschrift "## **Metabeschreibung**" fortgesetzt
- Vor dem Einleitungsabsatz steht KEINE Überschrift
- Alle Zwischenüberschriften verwenden genau das Format "## Überschrift" (H2)
- Nach jedem Abschnitt kommt eine Leerzeile

Sprachliche Vorgaben:
- Verwende eine moderne, progressive Sprache, die die Business Punk-Zielgruppe anspricht (25-40 Jahre, digital-affin, innovationsinteressiert)
- Nutze einen selbstbewussten, direkten Stil ohne überheblich zu wirken
- Setze gezielt 3-4 Anglizismen ein, aber nur dort, wo sie natürlich wirken und im Businesskontext gebräuchlich sind
- Verwende starke Adjektive wie "disruptiv" oder "innovativ" punktuell und zielgerichtet
- Baue prägnante Sätze mit 12-15 Wörtern, informationsdicht und ohne Füllwörter
- Wechsle zwischen direkten Hauptsätzen und ergänzenden Nebensatzkonstruktionen ab
- Nutze aktive Verben für Dynamik und Direktheit
- Fachbegriffe können ohne Erklärung verwendet werden (Business-affine Zielgruppe)
- Wechsle bei Unternehmensaussagen zwischen indirekter Rede im Konjunktiv I und direkten Zitaten ab

WICHTIG - Konjunktiv I: Verwende für indirekte Rede von Unternehmensaussagen, Studien oder Pressemitteilungen stets den Konjunktiv I

Qualitätskontrolle:
- War das allererste Element im Artikelbody der Einleitungsabsatz OHNE Überschrift davor?
- Modulare Struktur entsprechend des erkannten {primary_module}-Moduls korrekt angewandt?
- Business Punk-Stil: selbstbewusst, progressiv, direkt?
- Reality Check und FAQs thematisch perfekt aufeinander abgestimmt?
- Zielgruppengerecht für junge, digital-affine Business-Menschen?
- Format und Strukturvorgaben eingehalten?

**Anweisungen**:

# Formatierung
- Formatiere den gesamten Text in Markdown
- EXTREM WICHTIG: Kennzeichne die einzelnen Komponenten genau wie folgt:
  * Für den Titel: ## **Titel**
  * Für den Abstract: ## **Abstract**
  * Für den Artikelinhalt: ## **Artikelbody**
  * Für die Metabeschreibung: ## **Metabeschreibung**
  * Für die Keywords: ## **Keywords**
  * Für die FAQs: ## **Häufig gestellte Fragen**
  * Für den Business Punk Check: ## **Business Punk Check**
  * Für die Quellen: ## **Quellen**
- Verwende ** für Fettmarkierungen bei wichtigen Begriffen und Schlüsselwörtern
- EXTREM WICHTIG: Setze ALLE Zwischenüberschriften mit ## (H2) - niemals mit ### (H3) oder mehr
- Halte Absätze kurz und dynamisch (max. 5-6 Sätze)
- EXTREM WICHTIG: Die Einleitung hat NIEMALS eine Zwischenüberschrift

Hier ist der Entwurftext: {article_text}"""

    return generate_text_claude(complete_prompt)

def process_text_for_social_linkedin(result_text):
    """
    Updated LinkedIn Post Generator mit modulspezifischen Hashtags
    """
    # Erkenne das Modul aus dem generierten Text
    primary_module = analyze_theme_module(result_text)
    hashtags = get_social_media_hashtags(primary_module, 'linkedin')
    module_info = get_module_info(primary_module)
    
    prompt2 = f"""Erstelle einen LinkedIn-Post für Business Punk basierend auf dem folgenden Artikeltext.

🎯 ERKANNTES MODUL: {module_info['name']}
📊 MODULARER FOKUS: {module_info['focus']}

Der Post sollte die progressive Business Punk-Community ansprechen und folgende Elemente enthalten:

# Struktur und Stil
- Beginne mit einem prägnanten, aufmerksamkeitsstarken Hook (max. 150 Zeichen)
- Verwende den typischen Business Punk-Stil: direkt, selbstbewusst und präzise
- Baue 2-3 passende Emojis an strategischen Stellen ein
- Halte die Gesamtlänge zwischen 900-1100 Zeichen
- Sprich die Leser indirekt an (niemals "Du" oder "Sie" verwenden)

# Modulspezifische Anpassung für {primary_module}:
{get_module_specific_social_guidance(primary_module)}

# Inhaltliche Elemente
1. Eine pointierte Zusammenfassung der wichtigsten Erkenntnisse (max. 400 Zeichen)
2. Ein überraschendes Zitat oder eine unerwartete Zahl aus dem Artikel (max. 150 Zeichen)
3. Einen Bezug zu aktuellen Trends im {module_info['name']}-Bereich
4. UNBEDINGT: Diese spezifischen Hashtags verwenden: {' '.join(hashtags)}
5. Eine pointierte Frage oder einen Call-to-Action am Ende, der zur Diskussion anregt

# Wichtige Hinweise
- Verzichte auf konservative Business-Floskeln und typische LinkedIn-Phrasen
- Setze auf präzise Formulierungen und treffende Beobachtungen
- Verwende einen klaren, modernen Sprachstil mit SEHR SPARSAMER Verwendung von Anglizismen (maximal 2-3 im gesamten Post)
- Stelle einen klaren Bezug zur progressiven Zielgruppe (digitale Vordenker, Innovatoren, New Work-Enthusiasten) her
- Passe Sprache und Fokus an das primäre Themenmodul des Artikels an
- WICHTIG: Der Post MUSS IMMER alle angegebenen Hashtags enthalten

Hier ist der Text des Artikels: {result_text}"""

    return generate_text_claude(prompt2)

def process_text_for_social_facebook(result_text):
    """
    Updated Facebook Post Generator mit modulspezifischen Hashtags
    """
    # Erkenne das Modul aus dem generierten Text
    primary_module = analyze_theme_module(result_text)
    hashtags = get_social_media_hashtags(primary_module, 'facebook')
    module_info = get_module_info(primary_module)
    
    prompt3 = f"""Erstelle einen Facebook-Post für Business Punk basierend auf dem folgenden Artikeltext.

🎯 ERKANNTES MODUL: {module_info['name']}
📊 MODULARER FOKUS: {module_info['focus']}

Der Post sollte die progressive Business Punk-Community ansprechen und folgende Elemente enthalten:

# Struktur und Stil
- Beginne mit einer prägnanten Überschrift oder pointierten These (max. 100 Zeichen)
- Halte den gesamten Post kurz und auf den Punkt (max. 450 Zeichen)
- Verwende den charakteristischen Business Punk-Stil: selbstbewusst, klar und direkt
- Baue 2-3 strategisch platzierte, passende Emojis ein
- Sprich die Leser indirekt an (keine "Du"- oder "Sie"-Ansprache)

# Modulspezifische Anpassung für {primary_module}:
{get_module_specific_social_guidance(primary_module)}

# Inhaltliche Elemente
1. Eine aufmerksamkeitsstarke Einleitung, die sofort Interesse weckt (1-2 Sätze)
2. Einen überraschenden Fakt oder eine relevante Perspektive aus dem Artikel
3. Einen Bezug zu aktuellen Trends im {module_info['name']}-Bereich
4. UNBEDINGT: Diese spezifischen Hashtags verwenden: {' '.join(hashtags)}
5. Eine pointierte Frage oder einen Call-to-Action als Abschluss, der Interaktion fördert

# Wichtige Hinweise
- Der Ton sollte progressiv und gleichzeitig informativ sein
- Verzichte auf konservative Business-Floskeln und Standard-Social-Media-Phrasen
- Setze auf prägnante Formulierungen mit klarer Aussage
- Passe Fokus und Ton an das primäre Themenmodul des Artikels an
- Verwende Anglizismen SEHR SPARSAM - maximal 1-2 im gesamten Post und nur wenn unverzichtbar
- WICHTIG: Der Post MUSS IMMER alle angegebenen Hashtags enthalten

Hier ist der Text des Artikels: {result_text}"""

    return generate_text_claude(prompt3)

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
    """
    Hauptfunktion der Streamlit-App.
    """
    print("Starte Business Punk Article Generator")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.title("Generate Article from Multiple Sources")
        
        # Dropdown für die Artikellänge
        article_length = st.selectbox(
            "Select Article Length",
            options=["Short (300-400 words)", "Normal (650 words)", "Long (800-1000 words)"],
            index=1,  # "Normal" als Standard vorausgewählt
            key="article_length"
        )
        
        # Extrahiere die numerischen Werte aus dem Dropdown
        if "Short" in article_length:
            word_count = "300-400"
        elif "Normal" in article_length:
            word_count = "650"
        else:  # Long
            word_count = "800-1000"
        
        st.subheader("Input URLs")
        num_url_inputs = st.number_input("Number of URLs to process", min_value=0, max_value=5, value=1)
        urls = []
        for i in range(num_url_inputs):
            url = st.text_input(f"Enter URL {i+1}", key=f"url_{i}")
            if url:
                urls.append(url)
        
        user_text = st.text_area("Or enter the text you'd like to rewrite:", height=150)
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
                    print(f"Verarbeite {len(urls)} URLs")
                    original_text, url_contents = process_multiple_urls(urls)
                    source = ", ".join(urls)
                
                if user_text.strip():
                    print("Verarbeite benutzerdefinierten Text")
                    if original_text:
                        original_text += "\n\n" + user_text.strip()
                        source += " and user provided text"
                    else:
                        original_text = user_text.strip()
                        source = "User provided text"
                
                if uploaded_file is not None:
                    print("Verarbeite hochgeladene PDF-Datei")
                    pdf_text = process_pdf(uploaded_file)
                    if original_text:
                        original_text += "\n\n" + pdf_text
                        source += " and uploaded PDF"
                    else:
                        original_text = pdf_text
                        source = "Uploaded PDF"
                
                if original_text:
                    print(f"Generiere Artikel mit Claude (Länge: {word_count} Wörter)")
                    source_info = create_source_info(urls, uploaded_file, bool(user_text.strip()), url_contents if 'url_contents' in locals() else {})
                    result = process_text_for_seo(original_text, source_info, custom_instructions, word_count)
                    
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
                        st.title("Generated Article Content:")
                    
                        # Verbesserte Extraktion mit Debug-Ausgaben - GEÄNDERT: 8 Komponenten
                        components = extract_article_components(result)
                        if len(components) == 8 and components[0] and components[1] and components[2] and components[3]:
                            title, abstract, content, meta, keywords, reality_check, faqs, sources = components  # GEÄNDERT: reality_check hinzugefügt
                            print(f"Extraktion erfolgreich: {len(content)} Zeichen im Content")
                            
                            # Nur wenn tatsächlich Inhalt gefunden wurde
                            if content.strip():
                                api_response = api_send_fragment(title, abstract, content, meta, sources, "", faqs)
                                st.write("API Response:", api_response)
                                
                                # Session State setzen - GEÄNDERT: faqs hinzugefügt
                                # Session State setzen - GEÄNDERT: reality_check hinzugefügt
                                st.session_state['title'] = title
                                st.session_state['abstract'] = abstract  
                                st.session_state['content'] = content
                                st.session_state['meta'] = meta
                                st.session_state['keywords'] = keywords
                                st.session_state['faqs'] = faqs
                                st.session_state['sources'] = sources
                                
                            else:
                                st.error("Content-Extraktion fehlgeschlagen: Leerer Content gefunden")
                                st.info("Generierter Content wird angezeigt, aber nicht an die API gesendet")
                        else:
                            st.error("Extraktion fehlgeschlagen - nicht alle Komponenten gefunden:")
                            st.write(f"Title gefunden: {bool(components[0]) if len(components) > 0 else False}")
                            st.write(f"Abstract gefunden: {bool(components[1]) if len(components) > 1 else False}")
                            st.write(f"Content gefunden: {bool(components[2]) if len(components) > 2 else False}")
                            st.write(f"Meta gefunden: {bool(components[3]) if len(components) > 3 else False}")
                            st.write(f"Keywords gefunden: {bool(components[4]) if len(components) > 4 else False}")  # NEU
                            st.write(f"Business Punk Check gefunden: {bool(components[5]) if len(components) > 5 else False}")  # NEU
                            st.write(f"FAQs gefunden: {bool(components[6]) if len(components) > 6 else False}")  # NEU
                            st.write(f"Sources gefunden: {bool(components[7]) if len(components) > 7 else False}")  # NEU
                            st.info("Generierter Content wird angezeigt, aber nicht an die API gesendet")
                        
                        # Immer den Rohtext anzeigen
                        st.write(result)
                        
                        # Social Media Posts erstellen
                        print("Generiere LinkedIn-Post")
                        linkedin = process_text_for_social_linkedin(result)
                        st.title("LinkedIn Post:")
                        st.write(linkedin)
                        
                        print("Generiere Facebook-Post")
                        facebook = process_text_for_social_facebook(result)
                        st.title("Facebook Post:")
                        st.write(facebook)
                    
                    # Update Google Sheet
                    #current_date = time.strftime("%Y-%m-%d")
                    #current_time = time.strftime("%H:%M:%S")
                    #update_google_sheet(current_date, current_time, source, original_text, result, linkedin)
                else:
                    st.error("No content to process. Please provide URLs, enter text, or upload a PDF file.")

if __name__ == "__main__":
    main()