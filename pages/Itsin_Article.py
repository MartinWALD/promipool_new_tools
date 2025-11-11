from openai import OpenAI
import time
from rich import print
import requests
import pandas as pd
import streamlit as st
from newspaper import Article
from urllib.parse import urlparse
import json
import re
import PyPDF2
import io

# Page configuration
st.set_page_config(
    page_title="Itsin Article Generator - Multi-Format",
    page_icon="📱",
    layout="wide"
)

# WordPress/Gutenberg Configuration (wird später verwendet)
wp_url = "https://itsin.de/wp-json/wp/v2/posts"  # Anpassen wenn WordPress URL bekannt
# wp_auth_key = st.secrets.get("wp_itsin", "")  # Später in secrets.toml hinzufügen
category_ids = [1]  # Anpassen für Itsin-Kategorien

# Streamlit UI layout
col1, col2, col3 = st.columns(3)

def create_source_info_itsin(urls, uploaded_file=None, user_text_provided=False, url_contents=None):
    """
    Erstellt erweiterte Quelleninfo für Itsin Artikel (Influencer/Social Media-fokussiert)
    """
    from urllib.parse import urlparse

    def extract_domain_info(url):
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')

            # Itsin-relevante Influencer/Social Media-Quellen
            influencer_source_mapping = {
                # Social Media Plattformen
                'instagram.com': ('Instagram', 'Social Media Plattform Instagram', 'Influencer-Content und Creator-Updates'),
                'tiktok.com': ('TikTok', 'Video-Plattform TikTok', 'Viral-Content und Gen-Z-Trends'),
                'youtube.com': ('YouTube', 'Video-Plattform YouTube', 'Creator-Economy und Video-Trends'),
                'twitter.com': ('X/Twitter', 'Social Media Plattform X', 'Real-time Updates und Trending Topics'),
                'x.com': ('X', 'Social Media Plattform X', 'Real-time Updates und Trending Topics'),
                'facebook.com': ('Facebook', 'Social Media Plattform Facebook', 'Community-Updates'),
                'snapchat.com': ('Snapchat', 'Social Media App Snapchat', 'Gen-Z Content und Stories'),
                'twitch.tv': ('Twitch', 'Streaming-Plattform Twitch', 'Gaming und Live-Content'),

                # Influencer & Lifestyle News
                'promiflash.de': ('Promiflash', 'Celebrity-Portal Promiflash', 'Influencer-News und Social Media Trends'),
                'bild.de': ('Bild', 'Boulevard-Zeitung Bild', 'Influencer-Skandale und Viral-News'),
                'bunte.de': ('Bunte', 'People-Magazin Bunte', 'Influencer-Lifestyle und Promi-News'),
                'gala.de': ('Gala', 'Lifestyle-Magazin Gala', 'Celebrity und Influencer-Content'),
                'ok-magazin.de': ('OK! Magazin', 'Celebrity-Magazin OK!', 'Influencer-Gossip'),

                # Gen-Z/Millennial Media
                'vice.com': ('Vice', 'Jugend-Magazin Vice', 'Gen-Z-Kultur und Subkulturen'),
                'noizz.de': ('Noizz', 'Gen-Z-Magazin Noizz', 'Jugendkultur und Trends'),
                'buzzfeed.com': ('BuzzFeed', 'Online-Magazin BuzzFeed', 'Viral-Content und Pop-Kultur'),
                'refinery29.com': ('Refinery29', 'Lifestyle-Magazin Refinery29', 'Female-Creator-Content'),

                # Entertainment & Pop Culture
                'spotify.com': ('Spotify', 'Musik-Streaming Spotify', 'Musik-Trends und Podcast-Content'),
                'netflix.com': ('Netflix', 'Streaming-Dienst Netflix', 'Serie-Trends und Binge-Content'),
                'amazon.de': ('Amazon Prime', 'Streaming-Dienst Amazon Prime', 'Serie-News und Creator-Shows'),

                # Tech & Creator Tools
                'techcrunch.com': ('TechCrunch', 'Tech-Magazin TechCrunch', 'Creator-Economy und Social Media Tech'),
                'theverge.com': ('The Verge', 'Tech-Magazin The Verge', 'Social Media Updates und App-News'),
                'wired.com': ('Wired', 'Tech-Magazin Wired', 'Digital Culture und Influencer-Tech'),

                # News Portals (Entertainment/Social)
                'spiegel.de': ('Spiegel', 'Nachrichtenmagazin Spiegel', 'Social Media Trends und Jugendkultur'),
                'zeit.de': ('Zeit', 'Wochenzeitung Die Zeit', 'Influencer-Kultur und Gesellschaft'),
                'faz.de': ('FAZ', 'Frankfurter Allgemeine Zeitung', 'Creator-Economy Analyse'),
                't-online.de': ('t-online.de', 'Online-Portal t-online.de', 'Viral-News und Social Media'),
            }

            for key, (name, description, content_focus) in influencer_source_mapping.items():
                if key in domain.lower():
                    return domain, name, description, content_focus

            return domain, domain, f"Online-Quelle {domain}", "Social Media Informationen"

        except Exception:
            return url, url, f"Online-Quelle {url}", "allgemeine Informationen"

    if not url_contents:
        url_contents = {}

    source_info = "QUELLENVERZEICHNIS FÜR ITSIN ARTIKEL:\n"
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

def analyze_theme_module_itsin(article_text: str, source_info: str = "") -> str:
    """
    Erkennt die Itsin-Kategorie automatisch (Influencer/Social Media-fokussiert)
    """
    full_text = (article_text + " " + source_info).lower()

    modules = {
        'INFLUENCER': {
            'keywords': ['influencer', 'creator', 'content creator', 'youtuber', 'tiktoker', 'streamer', 'instagram', 'follower', 'social media star'],
            'high_priority': ['influencer', 'creator', 'tiktoker', 'youtuber']
        },
        'VIRAL_TRENDS': {
            'keywords': ['viral', 'trend', 'trending', 'challenge', 'meme', 'hype', 'foryou', 'fyp', 'viralvideo'],
            'high_priority': ['viral', 'trending', 'challenge', 'hype']
        },
        'BEAUTY_FASHION': {
            'keywords': ['beauty', 'fashion', 'style', 'makeup', 'skincare', 'outfit', 'look', 'styling', 'mode'],
            'high_priority': ['beauty', 'fashion', 'makeup', 'style']
        },
        'GAMING_ESPORTS': {
            'keywords': ['gaming', 'esports', 'gamer', 'streamer', 'twitch', 'spielen', 'game', 'konsole'],
            'high_priority': ['gaming', 'esports', 'twitch', 'streamer']
        },
        'RELATIONSHIP_LIFESTYLE': {
            'keywords': ['beziehung', 'dating', 'lifestyle', 'love', 'couple', 'paar', 'liebe', 'freund', 'freundin'],
            'high_priority': ['beziehung', 'dating', 'couple', 'lifestyle']
        },
        'MUSIC_ENTERTAINMENT': {
            'keywords': ['musik', 'song', 'album', 'konzert', 'festival', 'charts', 'spotify', 'rapper', 'sänger'],
            'high_priority': ['musik', 'song', 'album', 'konzert']
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
        return 'INFLUENCER'

    primary_module = max(scores, key=scores.get)
    return primary_module

def get_module_info_itsin(module_key: str) -> dict:
    """
    Gibt Informationen zur erkannten Itsin-Kategorie zurück
    """
    modules_info = {
        'INFLUENCER': {
            'name': 'Influencer & Creator',
            'focus': 'Influencer-News und Creator-Updates',
            'hashtags': ['#Influencer', '#Creator', '#SocialMedia', '#ContentCreator', '#Viral']
        },
        'VIRAL_TRENDS': {
            'name': 'Viral & Trends',
            'focus': 'Virale Trends und Social Media Challenges',
            'hashtags': ['#Viral', '#Trending', '#Challenge', '#FYP', '#TikTok']
        },
        'BEAUTY_FASHION': {
            'name': 'Beauty & Fashion',
            'focus': 'Beauty-Trends und Fashion-Content',
            'hashtags': ['#Beauty', '#Fashion', '#Makeup', '#Style', '#OOTD']
        },
        'GAMING_ESPORTS': {
            'name': 'Gaming & Esports',
            'focus': 'Gaming-News und Esports-Updates',
            'hashtags': ['#Gaming', '#Esports', '#Twitch', '#Gamer', '#Stream']
        },
        'RELATIONSHIP_LIFESTYLE': {
            'name': 'Relationship & Lifestyle',
            'focus': 'Dating-Tipps und Lifestyle-Content',
            'hashtags': ['#Relationship', '#Dating', '#Lifestyle', '#Love', '#Couple']
        },
        'MUSIC_ENTERTAINMENT': {
            'name': 'Music & Entertainment',
            'focus': 'Musik-News und Entertainment-Updates',
            'hashtags': ['#Music', '#Entertainment', '#Charts', '#Spotify', '#Konzert']
        }
    }

    return modules_info.get(module_key, modules_info['INFLUENCER'])

def extract_real_quotes_from_source_itsin(text):
    """
    Extrahiert direkte Zitate aus Influencer/Social Media Content
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
                'Menü', 'Ressorts', 'Newsletter', 'Abo', 'Login', 'Display'
            ]):
                if any(term in match.lower() for term in [
                    'ich', 'mein', 'mir', 'bin', 'habe', 'will', 'kann', 'möchte',
                    'liebe', 'freue', 'denke', 'glaube', 'finde', 'sage', 'würde',
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

def extract_sources_from_info_itsin(source_info):
    """
    Extrahiert Quellennamen für Zitierung
    """
    import re
    sources = []

    pattern = r'Quelle\s+\d+:\s+([^(]+)\s*\(([^)]+)\)'
    matches = re.findall(pattern, source_info)

    for description, domain in matches:
        if 'instagram' in description.lower():
            sources.append('Instagram')
        elif 'tiktok' in description.lower():
            sources.append('TikTok')
        elif 'youtube' in description.lower():
            sources.append('YouTube')
        elif 'bild' in description.lower():
            sources.append('Bild')
        else:
            clean_domain = domain.replace('www.', '').replace('.de', '').replace('.com', '')
            sources.append(clean_domain.capitalize())

    return sources

def extract_concrete_facts_itsin(text):
    """
    Extrahiert konkrete Influencer/Social Media-Fakten
    """
    import re
    facts = []

    patterns = [
        r'\d+(?:\.\d+)?\s*(?:Follower|Likes|Views|Abonnenten|Fans|Zuschauer)',
        r'\d+(?:\.\d+)?\s*(?:Millionen|Mio\.|Milliarden|Mrd\.)\s*(?:Follower|Likes|Views|Fans)',
        r'(?:ist|war|wurde)\s+\d{1,2}\s*(?:Jahre|Jahr)\s*(?:alt|jung)',
        r'seit\s+\d{1,4}\s*(?:verheiratet|zusammen|verlobt|getrennt)',
        r'(?:seit|vor|nach|in)\s+\d{4}',
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


def process_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def generate_text(prompt, model="gpt-4o", temperature=0.5, max_retries=3):
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
    Erweiterte Funktion zum Entfernen von Markdown-Formatierung.
    """
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1', text)
    text = re.sub(r'^\#{1,6}\s*(.+)', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,2}([^\*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'\_{1,2}([^\_]+)\_{1,2}', r'\1', text)
    text = text.replace('`', '')
    text = text.replace('> ', '')
    return text

def extract_video_article_components(article_result: str) -> tuple:
    """
    Extrahiert Headline, Artikeltext, Meta und Hashtags aus Video-Artikel (OHNE Untertitel/Abstract)
    """
    headline_pattern = r"Headline:\s*(.*?)\n+"
    meta_pattern = r"Metabeschreibung:\s*(.*?)(?:\nHashtags:|$)"
    hashtags_pattern = r"Hashtags:\s*(.*?)$"

    headline = re.search(headline_pattern, article_result, re.DOTALL)
    meta = re.search(meta_pattern, article_result, re.DOTALL)
    hashtags = re.search(hashtags_pattern, article_result, re.DOTALL | re.MULTILINE)

    content = article_result
    if headline:
        content = re.sub(headline_pattern, "", content, flags=re.DOTALL).strip()
    if meta:
        content = re.sub(r"Metabeschreibung:.*?(?:\nHashtags:.*?)?$", "", content, flags=re.DOTALL).strip()

    clean_headline = headline.group(1).replace('\n', ' ').strip() if headline else ""
    clean_content = re.sub(r"Artikeltext:\s*\n+", "", content, flags=re.MULTILINE).strip()
    clean_meta = meta.group(1).strip() if meta else ""
    clean_hashtags = hashtags.group(1).strip() if hashtags else ""

    clean_headline = clean_headline.replace('**', '').strip()
    clean_meta = clean_meta.replace('**', '').strip()

    return (
        clean_headline,
        clean_content,
        clean_meta,
        clean_hashtags
    )

def extract_article_components(article_result: str) -> tuple:
    """
    Extract components from GPT's output for standard article, keeping markdown intact.
    """
    title_pattern = r"Titel:\s*(.*?)\n+"
    subtitle_pattern = r"Untertitel:\s*(.*?)\n{2,}"
    abstract_pattern = r"Abstract:\s*(.*?)\n{2,}"
    meta_pattern = r"Metabeschreibung:\s*(.*?)(?:\nKeywords:|$)"

    title = re.search(title_pattern, article_result, re.DOTALL)
    subtitle = re.search(subtitle_pattern, article_result, re.DOTALL)
    abstract = re.search(abstract_pattern, article_result, re.DOTALL)
    meta = re.search(meta_pattern, article_result, re.DOTALL)

    content = article_result
    if title:
        content = re.sub(title_pattern, "", content, flags=re.DOTALL).strip()
    if subtitle:
        content = re.sub(subtitle_pattern, "", content, flags=re.DOTALL).strip()
    if abstract:
        content = re.sub(abstract_pattern, "", content, flags=re.DOTALL).strip()
    if meta:
        content = re.sub(r"Metabeschreibung:.*?(?:\nKeywords:.*?)?$", "", content, flags=re.DOTALL).strip()

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

def format_content_for_gutenberg(content: str, abstract: str = "") -> str:
    """
    Formatiert Content für WordPress Gutenberg-Editor (wie BPM)
    """
    import re

    formatted_content = ""

    # Abstract als erster Absatz
    if abstract:
        formatted_content += f'<!-- wp:paragraph -->\n<p><i>{abstract}</i></p>\n<!-- /wp:paragraph -->\n\n'

    if not content:
        return formatted_content

    # Überprüfe auf Überschriften
    if re.search(r'##\s+[^\n]+', content):
        sections = re.split(r'(##\s+[^\n]+)', content)

        # Einleitungsabsatz
        if sections and not sections[0].strip().startswith('##'):
            intro = sections.pop(0).strip()
            if intro:
                intro_paragraphs = intro.split('\n\n')
                for para in intro_paragraphs:
                    if para.strip():
                        formatted_content += f'<!-- wp:paragraph -->\n<p>{para.strip()}</p>\n<!-- /wp:paragraph -->\n\n'

        # Verarbeite Überschrift-Inhalt-Paare
        i = 0
        while i < len(sections):
            if i < len(sections) and sections[i].strip().startswith('##'):
                heading = sections[i].replace('##', '').strip()
                formatted_content += f'<!-- wp:heading {{"level":2}} -->\n<h2>{heading}</h2>\n<!-- /wp:heading -->\n\n'

            if i + 1 < len(sections) and not sections[i+1].strip().startswith('##'):
                paragraph_content = sections[i+1].strip()
                paragraphs = paragraph_content.split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        formatted_content += f'<!-- wp:paragraph -->\n<p>{para.strip()}</p>\n<!-- /wp:paragraph -->\n\n'
                i += 2
            else:
                i += 1
    else:
        # Fallback ohne Überschriften
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if para.strip():
                formatted_content += f'<!-- wp:paragraph -->\n<p>{para.strip()}</p>\n<!-- /wp:paragraph -->\n\n'

    return formatted_content

@st.experimental_fragment
def gutenberg_preview_fragment():
    """
    Zeigt WordPress Gutenberg Preview (wie BPM)
    """
    if 'content' not in st.session_state or 'abstract' not in st.session_state:
        st.warning("Please generate an article first before previewing.")
        return

    if st.button("📋 Preview Gutenberg Format"):
        content = st.session_state.get('content', '').strip()
        abstract = st.session_state.get('abstract', '').strip()

        with st.expander("WordPress Gutenberg Preview", expanded=True):
            st.write("=== Gutenberg-formatted Content ===")
            gutenberg_formatted = format_content_for_gutenberg(content, abstract)
            st.code(gutenberg_formatted, language="html")

def process_text_for_video_article_itsin(article_text: str, source_info: str = "", custom_instructions: str = "", article_length: str = "lang") -> str:
    """
    Video-Artikel-Generator für Itsin mit neutraler Tonalität (Influencer-Themen)
    article_length: "lang" (150-180 Wörter) oder "kurz" (100-120 Wörter)
    """
    primary_module = analyze_theme_module_itsin(article_text, source_info)
    module_info = get_module_info_itsin(primary_module)

    print(f"🎯 Erkannte Itsin-Kategorie: {module_info['name']} ({primary_module})")
    print(f"📊 Video-Artikel {article_length.upper()}")

    real_quotes = extract_real_quotes_from_source_itsin(article_text)
    concrete_facts = extract_concrete_facts_itsin(article_text)
    available_sources = extract_sources_from_info_itsin(source_info)

    word_count = "150-180 Wörter" if article_length == "lang" else "100-120 Wörter"

    base_prompt = f"""KRITISCHE ANTI-HALLUZINATIONS-REGELN FÜR ITSIN VIDEO-ARTIKEL - STRIKT BEFOLGEN:

VIDEO-ARTIKEL BESONDERHEITEN:
- NEUTRALE TONALITÄT: Keine direkte Ansprache mit "Sie" oder "Du"
- STATTDESSEN: "Influencer können...", "Creator sollten...", "Die Followerin hat..."
- KEINE ZWISCHENÜBERSCHRIFTEN: Durchgehender Fließtext
- EXTREM KURZ UND PRÄGNANT: {word_count} - STRIKT EINHALTEN!
- FAKTENORIENTIERT: Weniger emotional/dramatisch als Standard-Artikel
- KEIN GESCHWAFEL: Nur die wichtigsten Kern-Informationen
- INFLUENCER-FOKUS: Auf Social Media und Creator-Content konzentrieren

1. QUELLEN UND ZITATE (Influencer/Social Media-fokussiert):
    - Verfügbare Quellen: {', '.join(available_sources) if available_sources else 'Nutze die Quellen aus der Quellenliste'}

   WICHTIG FÜR ITSIN-QUELLENANGABEN:
    - ALLE Quellennamen im Text IMMER kursiv: *Instagram*, *TikTok*, *YouTube*, *Bild.de*
    - IMMER kursiv hervorgehoben: laut *Instagram*
    - FORMAT: laut *Quelle*, *Quelle* berichtet, wie *Quelle* meldet
    - BEISPIELE: laut *Instagram*, so *TikTok*, wie *YouTube* berichtet

   ZITATE (Influencer/Creator-Fokus):
    - ABSOLUT KRITISCH: JEDES Creator-Zitat SOFORT mit Quelle
    - Format: „Zitat hier", so *Quellenname*
    - WORTGETREUE ÜBERNAHME: Creator-Zitate müssen EXAKT übernommen werden
    - DEUTSCHE ÜBERSETZUNG: Alle Zitate müssen ins Deutsche übersetzt werden

VERFÜGBARE ECHTE CREATOR-ZITATE AUS DEM ORIGINALTEXT:
{chr(10).join([f'• "{quote}" (direkte Aussage)' for quote in real_quotes[:3]]) if real_quotes else '• Keine direkten Creator-Zitate im Originaltext gefunden - verwende nur indirekte Rede'}

VERFÜGBARE INFLUENCER-FAKTEN:
{chr(10).join([f'• {fact[:100]}...' for fact in concrete_facts[:3]]) if concrete_facts else '• Nutze nur Fakten aus dem bereitgestellten Originaltext'}

ERKANNTE ITSIN-KATEGORIE: {primary_module} ({module_info['name']})
KATEGORIE-FOKUS: {module_info['focus']}

VIDEO-ARTIKEL STIL-REGELN:
- NEUTRALE SPRACHE: Keine "Sie"/"Du"-Ansprache
- RICHTIG: "Creator können von der Entwicklung profitieren"
- FALSCH: "Du kannst von der Entwicklung profitieren"
- RICHTIG: "Influencerin Name hat sich geäußert"
- FALSCH: "Die Influencerin, bekannt aus..., hat sich geäußert"
- FAKTENBASIERT: Direkte Informationsvermittlung ohne emotionale Überhöhung
- KLAR UND PRÄZISE: Kurze Sätze, keine Verschachtelungen
- KEINE AUSRUFEZEICHEN: Sachlicher Ton durchgehend

ANTI-KI-STIL FÜR VIDEO-ARTIKEL:
- KEINE Komma-Einschübe nach Namen: "Name, der/die..." ist verboten
- DIREKT beginnen: "Influencerin Name" oder einfach "Name"
- KEINE emotionalen Verstärker: "endlich", "überraschend", "sensation"
- SACHLICH bleiben: Fakten präsentieren, nicht dramatisieren

QUELLENNUTZUNG (Video-Artikel):
- Verfügbare Quellen: {', '.join([f'*{source}*' for source in available_sources])}
- ALLE Quellennamen KURSIV: *Instagram*, *TikTok*, *YouTube*
- SPARSAM verwenden: 2-3 Quellenangaben im gesamten Artikel
- NUR bei direkten Zitaten oder wichtigen Fakten

{source_info}

INFLUENCER-QUELLENTEXT:
{article_text}

KRITISCHE ERINNERUNG:
- {word_count} einhalten
- KEINE Zwischenüberschriften
- NEUTRALE Tonalität ohne direkte Ansprache
- ALLE Zitate müssen ins Deutsche übersetzt werden
- Quellen KURSIV: *Quellenname*
"""

    if custom_instructions.strip():
        base_prompt += f"\n\nWICHTIG: Zusätzliche spezifische Anweisungen für diesen Video-Artikel:\n{custom_instructions}"

    complete_prompt = base_prompt + f"""
📹 FORMAT: Video-Artikel ({article_length.upper()})
📝 STRUKTUR: NUR Headline + Fließtext OHNE Zwischenüberschriften (###)
🎯 HOOK: Starker Einstieg in den ersten 2 Sätzen
#️⃣ HASHTAGS: 5-7 relevante Hashtags am Ende (PFLICHT!)

Der Video-Artikel muss folgende Elemente enthalten:

Headline: Entwickle eine prägnante Headline (max. 60 Zeichen), die das Hauptthema klar benennt. Keine Ausrufezeichen.

WICHTIG: KEIN Untertitel! KEIN Abstract! Direkt mit Artikeltext starten!

Artikeltext: Der Video-Artikel soll EXAKT {word_count} umfassen - NICHT MEHR!

⚠️ ANTI-GESCHWAFEL-REGELN (KRITISCH!):
- NUR die 3-4 wichtigsten Kern-Fakten
- KEINE ausschweifende Creator-Biografie oder Karriere-Details
- MINIMALER Hintergrund - nur wenn ABSOLUT notwendig
- FOKUS auf die AKTUELLE Story/Nachricht
- Jeder Satz muss ESSENTIAL sein - sonst raus!

🎣 HOOK-REGEL (KRITISCH!):
- Die ersten 1-2 Sätze = ALLES!
- Starte mit der wichtigsten Information oder einer konkreten Zahl/Datum
- RICHTIG: "Influencerin Name verkündet am 10. November ihre Schwangerschaft auf Instagram."
- FALSCH: "Eine überraschende Nachricht erreicht die Social Media Welt..."

WICHTIGE REGELN FÜR VIDEO-ARTIKEL:
- KEINE Zwischenüberschriften - durchgehender Fließtext
- KEINE direkte Ansprache (Sie/Du)
- NEUTRALE Formulierung: "Creator können...", "Die Influencerin verkündete..."
- EXTREM KURZ: {word_count} - STRIKT EINHALTEN!
- FAKTENBASIERT: Weniger emotional als Standard-Artikel
- Quellen IMMER KURSIV: laut *Instagram*, so *TikTok* berichtet
- NIEMALS Quellen in Anführungszeichen: laut "Instagram" ist FALSCH
- KEINE Ausrufezeichen
- Direkte Zitate NUR wenn essentiell: „Zitat", so *Quelle*

Metabeschreibung: Am Ende des Artikels, füge eine prägnante SEO-Metabeschreibung hinzu (150-160 Zeichen).

Besonderheiten:
Alle verwendeten Zitate müssen wörtlich und unverändert aus dem Entwurf übernommen werden.
Übersetze Zitate immer in deutsche Sprache.
WICHTIG: SETZE IMMER DIE KOMBINATION AUS VOR- UND NACHNAME.
WICHTIG: Verwende korrekte Quellenangaben IMMER KURSIV: *Instagram*, *TikTok*, *YouTube*
WICHTIG: NIEMALS Quellenangaben in Anführungszeichen
WICHTIG: KEINE Zwischenüberschriften im Artikeltext
WICHTIG: KEIN Untertitel, KEIN Abstract

Checkliste:
Sind {word_count} STRIKT eingehalten? (Nicht mehr!)
Ist KEIN Geschwafel enthalten? (Nur Kern-Fakten!)
Ist die neutrale Tonalität durchgehend (kein "Sie"/"Du")?
Startet der Artikel mit einem starken Hook?
Sind ALLE Quellenangaben kursiv (*Quelle*) und NICHT in Anführungszeichen?
Gibt es KEINE Zwischenüberschriften im Artikeltext?
Gibt es KEINEN Untertitel und KEIN Abstract?
Sind 5-7 Hashtags am Ende?

Der Artikel muss die folgenden Komponenten beinhalten und genau so formatiert sein:

Headline:
[Deine Headline OHNE ** oder andere Formatierung]

Artikeltext:
[Hier kommt der Haupttext als durchgehender Fließtext OHNE Zwischenüberschriften, OHNE Bulletpoints, mit korrekten kursiven Quellenangaben. MAXIMAL {word_count}!]

[Optional: Weiterer kurzer Absatz - nur wenn noch unter {word_count}]

Formatierungsregeln:
- KEINE Sternchen (**) um Headline oder Metabeschreibung
- KEINE Zwischenüberschriften (### verboten!)
- Lasse immer eine Leerzeile zwischen Absätzen
- Quellen IMMER KURSIV: *Instagram* (mit einfachen Sternchen)
- NIEMALS Quellen in Anführungszeichen: "Instagram" ist FALSCH
- Keine Anführungszeichen außer bei direkten Zitaten
- KEIN Geschwafel - nur Essential Facts!

Metabeschreibung:
[Deine Metabeschreibung OHNE ** oder Formatierung]

Hashtags:
[5-7 relevante Hashtags für Social Media, z.B. #Influencer #SocialMedia #Creator #Viral #TikTok]

Hier ist der Text des Entwurfsartikels: {article_text}"""

    result = generate_text(complete_prompt)
    result = convert_source_quotes_to_german(result)
    return result

def process_text_for_seo_enhanced_itsin(article_text: str, source_info: str = "", custom_instructions: str = "") -> str:
    """
    Erweiterte SEO-Funktion für Itsin (Influencer-Themen, leicht weniger emotional als Promipool)
    """
    primary_module = analyze_theme_module_itsin(article_text, source_info)
    module_info = get_module_info_itsin(primary_module)

    print(f"🎯 Erkannte Itsin-Kategorie: {module_info['name']} ({primary_module})")
    print(f"📊 Fokus: {module_info['focus']}")

    real_quotes = extract_real_quotes_from_source_itsin(article_text)
    concrete_facts = extract_concrete_facts_itsin(article_text)
    available_sources = extract_sources_from_info_itsin(source_info)

    base_prompt = f"""KRITISCHE ANTI-HALLUZINATIONS-REGELN FÜR ITSIN - STRIKT BEFOLGEN:

1. QUELLEN UND ZITATE (Influencer/Social Media-fokussiert):
    - Verfügbare Influencer/Social Media-Quellen: {', '.join(available_sources) if available_sources else 'Nutze die Quellen aus der Quellenliste'}

   WICHTIG FÜR ITSIN-QUELLENANGABEN:
    - ALLE Quellennamen im Text IMMER kursiv: *Instagram*, *TikTok*, *YouTube*, *Bild.de*
    - IMMER kursiv hervorgehoben: laut *Instagram*
    - FORMAT: laut *Quelle*, *Quelle* berichtet, wie *Quelle* meldet
    - BEISPIELE: laut *Instagram*, so *TikTok*, wie *YouTube* berichtet

   ZITATE (Creator/Influencer-Fokus):
    - ABSOLUT KRITISCH: JEDES Creator-Zitat SOFORT mit Quelle
    - Format: „Zitat hier", so *Quellenname*
    - WORTGETREUE ÜBERNAHME: Creator-Zitate müssen EXAKT übernommen werden
    - DEUTSCHE ÜBERSETZUNG: Alle Zitate müssen ins Deutsche übersetzt werden

   FAKTEN-QUELLENANGABEN (1x pro Absatz):
    - EXTREM WICHTIG mindestens eine strategische Quellenangabe pro Absatz
    - WANN: Bei wichtigen Creator-News, Follower-Zahlen, kontroversen Aussagen
    - FORMAT: laut *Quellenname*, so *Quellenname* berichtet, wie *Quellenname* meldet

   ANFÜHRUNGSZEICHEN-VERBOT:
    - NIEMALS Anführungszeichen um Inhalte setzen, die im Original keine haben
    - Indirekte Rede bleibt OHNE Anführungszeichen
    - NUR echte Creator-Direktzitate aus den Quellen in Anführungszeichen

2. INFLUENCER-QUELLENVERTEILUNG:
    - Verfügbare Quellen: {', '.join(available_sources) if available_sources else 'Instagram, TikTok, YouTube'}
    - ALLE Quellennamen immer kursiv: *Instagram*, *TikTok*, *YouTube*
    - VARIATION PFLICHT - verwende unterschiedliche Formulierungen: laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | *Quelle* enthüllt
    - NIEMALS die gleiche Formulierung zweimal verwenden!
    - Balance: Wichtige Creator-Facts MIT Quelle, Allgemeinwissen OHNE Quelle

VERFÜGBARE ECHTE CREATOR-ZITATE AUS DEM ORIGINALTEXT:
{chr(10).join([f'• "{quote}" (direkte Aussage)' for quote in real_quotes[:5]]) if real_quotes else '• Keine direkten Creator-Zitate im Originaltext gefunden - verwende nur indirekte Rede'}

    WICHTIGE ZITAT-VERWENDUNGSREGELN (Influencer):
    - Verwende die oben aufgelisteten echten DIREKTZITATE WÖRTLICH (keine Änderungen!)
    - NUR direkte Aussagen von Personen verwenden - keine Insider-Interpretationen
    - Jedes verwendete Zitat MUSS mit der korrekten Quelle versehen werden
    - Format: „Creator-Zitat hier", so *Quellenname*
    - Falls keine direkten Zitate verfügbar: NUR indirekte Rede im Konjunktiv I verwenden
    - NIEMALS eigene Creator-Zitate erfinden - nur die oben gelisteten verwenden!
    - ALLE Zitate müssen ins Deutsche übersetzt werden

    FOCUS: Direkte Aussagen von Influencern/Creatorn > Insider-Spekulationen

    ZUSATZ BEI MEHRFACHQUELLEN:
    - Wenn ein Zitat in MEHREREN Quellen steht, schreibe: "so berichten mehrere Medien"
    - Bei unsicherer Quelle: "wie verschiedene Medien zitieren"

VERFÜGBARE INFLUENCER-FAKTEN:
{chr(10).join([f'• {fact[:100]}...' for fact in concrete_facts[:5]]) if concrete_facts else '• Nutze nur Fakten aus dem bereitgestellten Originaltext'}

ERKANNTE ITSIN-KATEGORIE: {primary_module} ({module_info['name']})
KATEGORIE-FOKUS: {module_info['focus']}

    ITSIN-STIL OPTIMIERUNG (leicht weniger emotional als Promipool, aber jung und modern):
    - Nutze abwechslungsreiche Quellenangaben - NIEMALS dieselbe Formulierung zweimal:
    * laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | *Quelle* enthüllt
    - Verwende moderne, junge Sprache:
    * "krass" statt "bemerkenswert" | "mega" statt "sehr" | "nice" statt "angenehm"
    - Baue moderate Spannung auf: "Das wird spannend" | "Jetzt wird es interessant" | "Endlich Klarheit"
    - ITSIN-SPRACHE: "viral gegangen", "gedropt", "Hype", "Beef", "Call-out"
    - Beginne Sätze dynamischer: "Wow!", "Krass!", "Überraschung!", "Endlich!"
    - Max. 2-3 Ausrufezeichen im ganzen Artikel für Betonung
    - WICHTIG: Authentisch bleiben - keine übertriebene Jugendsprache!

    ITSIN ANTI-KI-STIL REGELN - STRIKT BEFOLGEN:
    - ABSOLUTES VERBOT: "Person, die bekannte...", "Person, bekannt aus..."
    - NIEMALS: "Name, der/die [Beschreibung], hat..." Struktur verwenden
    - SOFORT STOPPEN bei Komma-Einschüben nach Personennamen
    - RICHTIG: "Influencerin Name" oder einfach "Name"
    - FALSCH-BEISPIEL: "Lisa Müller, bekannt von TikTok"
    - RICHTIG-BEISPIEL: "TikTokerin Lisa Müller"

    ITSIN ANTI-KI-FLOSKEL REGELN:
    - VERMEIDE Standard-KI-Phrasen wie:
    * "könnte der Wendepunkt sein" → "bringt Bewegung rein"
    * "anheizt die Spekulationen" → "sorgt für Wirbel"
    * "sorgten für Aufsehen" → "ging viral"
    * "wollte sich nicht äußern" → "schweigt"

    ITSIN-SPRACHE STATT KI-SPRACHE:
    - NICHT: "Das Statement könnte wegweisend sein"
    - BESSER: "Das Statement sorgt für Diskussionen"
    - NICHT: "Die Beziehung bleibt angespannt"
    - BESSER: "Die beiden folgen sich nicht mehr"
    - NICHT: "weitere Posts erschwert"
    - BESSER: "postet nichts mehr"

    VERBOTENE SATZKONSTRUKTIONEN:
    - "[Name], bekannt aus [Plattform], hat..."
    - "[Name], die/der beliebte [Beruf], hat..."
    - "[Name], [Alter], ist..."
    - IMMER direkt beginnen: "[Beruf] [Name]" oder "[Name]"

    EMOTIONALE ITSIN-WENDUNGEN:
    - "ging viral", "trendet", "räumt auf", "dropt Bombe"
    - "sorgt für Hype", "eskaliert", "Call-out", "Beef"
    - "Drama", "Tea", "Receipts", "cancelled"

    ITSIN-STIL VERSTÄRKEN:
    - Mehr direkte Sprache: "Name postet" statt "Name veröffentlichte einen Post"
    - Modernere Verben: "droppen", "posten", "teilen", "shaden"
    - Influencer-Vokabular: "Follower-Count", "Story", "Post", "Video", "Trend"
    - Persönlicher: Vornamen verwenden (gelegentlich)
    - Spannung: "Was ist da los?", "Wie geht es weiter?"

    VERMEIDE DIESE KI-TRIGGER-WÖRTER:
    - "könnte", "möglicherweise", "allerdings", "jedoch", "dennoch" (zu häufig)
    - "offenbar", "berichten zufolge", "heißt es" (zu passiv)
    - "dies", "diese", "jene" (zu unpersönlich)
    - Meide KI-typische Wendungen: "dies führte zu", "dies sorgte für"
    - "die bekannte", "der beliebte", "die erfolgreiche" (KI-Einschübe)
    - Komma-Einschübe generell minimieren

    NATÜRLICHE DEUTSCHE ALTERNATIVEN:
    - STATT: "Lisa Müller, die bekannte TikTokerin, hat..."
    - BESSER: "TikTokerin Lisa Müller hat..." oder "Lisa Müller hat..."
    - STATT: "Der frischgebackenen Influencer-Mama geht es gut"
    - BESSER: "Müller geht es gut" oder "Der Familie geht es gut"
    - STATT: "die beliebte Influencerin"
    - BESSER: "Influencerin" oder "Müller"

    QUELLENNUTZUNG MIT ITSIN-FINGERSPITZENGEFÜHL:
    - Verfügbare Quellen: {', '.join([f'*{source}*' for source in available_sources])}
    - ZIEL: Alle Quellen verwenden, aber organisch und lesbar verteilt
    - BALANCE: Pro Absatz maximal 1-2 strategische Quellenangaben
    - VARIATION PFLICHT: Jede Quelle mit unterschiedlicher Formulierung:
    * laut *Quelle* | *Quelle* berichtet | wie *Quelle* meldet | heißt es bei *Quelle* | *Quelle* enthüllt
    - WANN zitieren: Bei wichtigen Facts, Enthüllungen, Zitaten, Drama
    - WANN NICHT: Bei Übergängen, Erklärungen, Allgemeinwissen
    - NATÜRLICHER FLUSS wichtiger als Quellenanzahl!

    QUELLENANGABEN-BALANCE (Fingerspitzengefühl):
    - NICHT jeder Satz braucht eine Quelle - das wirkt überladen!
    - PRO ABSATZ: Maximal 1-2 strategische Quellenangaben
    - ZITATE: Jedes echte Zitat braucht SOFORT eine Quellenangabe
    - FAKTEN: Wichtige Daten/Zahlen mit Quelle, aber nicht übertreiben
    - NATÜRLICHER FLUSS: Quelle dort einfügen, wo sie organisch passt

{source_info}

INFLUENCER-QUELLENTEXT:
{article_text}

KRITISCHE ERINNERUNG:
- JEDES Creator-Zitat braucht SOFORT eine Quellenangabe
- Pro Absatz EINE strategische Quellenangabe bei wichtigen Facts
- Qualität vor Quantität bei Quellenangaben
- ALLE Zitate müssen ins Deutsche übersetzt werden

ANTI-HALLUZINATIONS-REGEL FÜR TITEL/UNTERTITEL:
- NIEMALS vergangene Ereignisse als aktuell darstellen
- UNTERSCHEIDE klar: "plant Post" ≠ "hat gepostet"
- TIMELINE beachten: Was ist passiert vs. was ist geplant
- TITEL muss zum aktuellen Stand passen

Erstellen Sie einen SEO-optimierten journalistischen Artikel für junge Zielgruppe (Influencer/Social Media-Fokus), der Informationen aus dem Artikelentwurf zusammenfasst. Behalten Sie beim Umschreiben alle Fakten und Daten bei und verwenden Sie einzigartige Satzstrukturen und Formulierungen.

Wichtig: Direkte Zitate aus dem Entwurf müssen exakt und unverändert übernommen werden. Es darf keine Änderung an der Wortwahl, Grammatik oder am Satzbau der Zitate vorgenommen werden. Du kannst jedoch entscheiden, welche Zitate in den Artikel aufgenommen werden sollen.
WICHTIG: ALLE ZITATE MÜSSEN INS DEUTSCHE ÜBERSETZT WERDEN."""

    if custom_instructions.strip():
        base_prompt += f"\n\nWICHTIG: Zusätzliche spezifische Anweisungen für diesen Itsin-Artikel:\n{custom_instructions}"

    complete_prompt = base_prompt + f"""
    Der Artikel muss folgende Elemente enthalten:

    Titel: Entwickle einen MODERNEN und ANSPRECHENDEN Titel (max. 60 Zeichen), der junge Zielgruppen anspricht. Nutze Influencer-Vokabular wie "viral", "gedropt", "Hype", "Drama". Der Titel soll zum Klicken animieren, relevante Keywords enthalten und zur {module_info['name']}-Kategorie passen. Leicht weniger dramatisch als Promipool, aber modern und catchy.

    Untertitel: Formuliere einen prägnanten Untertitel mit MAXIMAL 3-4 Wörtern (max. 20 Zeichen)

    Abstract: Verfasse ein neugierig machendes Abstract im modernen Stil, das den Artikel anteast ohne zu viel zu verraten, relevante Schlüsselwörter aus der {module_info['name']}-Kategorie enthält und zum Weiterlesen animiert.

    ABSTRACT ANTI-SPOILER REGELN:
    - NICHT verraten: Genaue Details, spezifische Zahlen, konkrete Ergebnisse
    - STATTDESSEN: Andeutungen machen ("sorgt für Aufsehen", "krasse News", "überraschende Wendung")
    - NEUGIERIG MACHEN: Offene Fragen schaffen, Spannung aufbauen
    - KEYWORDS nutzen aber Details weglassen: Name + Thema erwähnen, aber nicht das konkrete Ergebnis verraten
    - BALANCE: Genug Information um Interesse zu wecken, aber Hauptenthüllungen für den Artikel aufsparen

    Artikeltext: Der Artikel soll ausführlich sein und die Informationen des ursprünglichen Entwurfs wiedergeben. Strukturiere den Text in mehrere Absätze mit passenden Zwischenüberschriften. Der erste Absatz des Artikeltextes soll keine Zwischenüberschrift bekommen. Verwende moderne, junge Sprache und Ausrufezeichen zur Betonung. Achte darauf, alle Fakten und Daten korrekt zu übernehmen. Wenn Zitate verwendet werden, müssen sie wörtlich und unverändert übernommen werden. Stellen Sie sicher, dass alle im Entwurf erwähnten Themen im Artikel behandelt werden.

    Metabeschreibung: Am Ende des Artikels, füge eine prägnante und nach SEO-Best Practices erstellte Metabeschreibung hinzu, die 150-160 Zeichen nicht überschreitet und den Inhalt des Artikels zusammenfasst.

    Bitte beachte, dass der Artikel einen journalistischen, sachlichen Ton wahren soll, ohne den Leser persönlich anzusprechen. Vermeide ein Schlusswort oder Fazit am Ende des Textes.

    Besonderheiten:
    Wähle sorgfältig aus, welche Zitate aus dem Entwurf in den Artikel aufgenommen werden sollen.
    Alle verwendeten Zitate müssen wörtlich und unverändert aus dem Entwurf übernommen werden.
    Übersetze Zitate immer in deutsche Sprache.
    WICHTIG: SETZE IMMER DIE KOMBINATION AUS VOR- UND NACHNAME.
    WICHTIG: LASSE KEINE RELEVANTEN INFORMATIONEN AUS DEN ENTWURFSQUELLEN AUS
    WICHTIG: Verwende korrekte Quellenangaben kursiv: *Instagram*, *TikTok*, *YouTube*
    Der restliche Artikel soll vollständig umgeschrieben werden.
    Versuche Dopplungen im Text zu vermeiden.

    Checkliste:
    Sind alle Zitate korrekt ins Deutsche übersetzt?
    Sind die Zitate unverändert übernommen worden?
    Ist überall Vor- und Nachname gesetzt worden?
    Sind alle relevanten Informationen aus den Entwurfsquellen übernommen wurden?
    Sind korrekte Quellenangaben kursiv hervorgehoben worden?
    Wurden nur die verfügbaren echten Zitate verwendet?
    Ist die Sprache modern und für junge Zielgruppen geeignet?

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
    - Keine Sternchen (*) für Formatierung außer für kursive Quellenangaben
    - Keine Anführungszeichen außer bei direkten Zitaten
    - Keine Zwischenüberschrift vor dem ersten Absatz
    - Quellenangaben immer kursiv: laut *Instagram*, so *TikTok* berichtet
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
        st.title("Itsin Article Generator")
        st.caption("Multi-Format Tool für Influencer-Content")

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
            help="Add specific instructions for tone, style, or focus areas.",
            placeholder="Example: 'Fokus auf TikTok-Aspekte' or 'Mehr Influencer-Hintergrund'",
            height=150
        )

        uploaded_file = st.file_uploader("Or upload a PDF file:", type="pdf")

        st.warning("If URL scraping doesn't work, we'll try using Jina.ai as a fallback.", icon="⚠️")

        if st.button("Generate Articles from Sources"):
            with st.spinner('Creating Articles from the provided data...'):
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
                    source_info = create_source_info_itsin(urls, uploaded_file, bool(user_text.strip()), url_contents if 'url_contents' in locals() else {})

                    # 1. Standard Artikel
                    st.info("📰 Generiere Standard-Artikel (400-600 Wörter)...")
                    result_standard = process_text_for_seo_enhanced_itsin(original_text, source_info, custom_instructions)

                    # 2. Video-Artikel Lang
                    st.info("🎬 Generiere Video-Artikel Lang (150-180 Wörter, neutral)...")
                    result_video_lang = process_text_for_video_article_itsin(original_text, source_info, custom_instructions, article_length="lang")

                    # 3. Video-Artikel Kurz
                    st.info("🎬 Generiere Video-Artikel Kurz (100-120 Wörter, neutral)...")
                    result_video_kurz = process_text_for_video_article_itsin(original_text, source_info, custom_instructions, article_length="kurz")

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
                            # ==================== STANDARD ARTIKEL ====================
                            st.markdown("## 📰 Standard Artikel")
                            st.markdown("*400-600 Wörter, moderner Stil für junge Zielgruppen, Zwischenüberschriften*")
                            st.markdown("---")

                            title_std, subtitle_std, abstract_std, content_std, meta_std = extract_article_components(result_standard)

                            st.markdown(f"""
**Titel:** {title_std}

**Untertitel:** {subtitle_std}

**Abstract:** {abstract_std}

**Artikeltext:**
{content_std}

**Metabeschreibung:** {meta_std}
""")

                            # Session State für Standard-Artikel (für Gutenberg-Export)
                            st.session_state['title'] = title_std
                            st.session_state['subtitle'] = subtitle_std
                            st.session_state['abstract'] = abstract_std
                            st.session_state['content'] = content_std
                            st.session_state['meta'] = meta_std

                            st.markdown("---")
                            st.markdown("")

                            # ==================== VIDEO-ARTIKEL LANG ====================
                            st.markdown("## 🎬 Video-Artikel Lang")
                            st.markdown("*150-180 Wörter, neutrale Tonalität, keine Zwischenüberschriften*")
                            st.markdown("---")

                            headline_vl, content_vl, meta_vl, hashtags_vl = extract_video_article_components(result_video_lang)

                            st.markdown(f"""
**Headline:** {headline_vl}

**Artikeltext:**
{content_vl}

**Metabeschreibung:** {meta_vl}

**Hashtags:** {hashtags_vl}
""")

                            st.markdown("---")
                            st.markdown("")

                            # ==================== VIDEO-ARTIKEL KURZ ====================
                            st.markdown("## 🎬 Video-Artikel Kurz")
                            st.markdown("*100-120 Wörter, neutrale Tonalität, keine Zwischenüberschriften*")
                            st.markdown("---")

                            headline_vk, content_vk, meta_vk, hashtags_vk = extract_video_article_components(result_video_kurz)

                            st.markdown(f"""
**Headline:** {headline_vk}

**Artikeltext:**
{content_vk}

**Metabeschreibung:** {meta_vk}

**Hashtags:** {hashtags_vk}
""")

                            st.markdown("---")

                            # WordPress/Gutenberg Optionen
                            st.markdown("### 📋 WordPress Export")
                            st.info("ℹ️ Standard-Artikel kann als Gutenberg-Format exportiert werden")
                            gutenberg_preview_fragment()

                        if st.query_params.get("dt") == "1":
                            with st.expander("Debug Output:"):
                                st.subheader("Debug Output:")
                                st.write(f"**Scraped Content:** {original_text}")

                else:
                    st.error("No content to process. Please provide URLs, enter text, or upload a PDF file.")

if __name__ == "__main__":
    main()
