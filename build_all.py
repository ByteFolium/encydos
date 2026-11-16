# ==============================================================================
# ENCYDOS Build Pipeline
# Copyright (c) 2026 ByteFolium
# 
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
#
# ------------------------------------------------------------------------------
# ARCHITECTURE OVERVIEW:
# This script transforms a 2008 MediaWiki static HTML dump into a lightweight,
# 8.3 compliant, pure ASCII archive designed for MS-DOS and Arachne 1.70.
# 
# It operates in four distinct phases:
#   1. Scanning: Maps long Wikipedia titles to strict 8.3 DOS filenames.
#   2. Redirects: Resolves Wikipedia redirects to their final destination.
#   3. Sanitization: Strips modern CSS/JS/images, fixes layout for VGA, and 
#      converts complex MediaWiki templates into basic HTML tables.
#   4. Indexing: Generates the A-Z navigation, the 2008 calendar, and the 
#      analog "Dice Function" search grid.
# ==============================================================================

import os
import re
import shutil
import hashlib
import html.entities
import unicodedata
from urllib.parse import unquote
from bs4 import BeautifulSoup, Comment, NavigableString
from collections import defaultdict

# --- CONFIGURATION ---
# The source directory containing the raw 2008 HTML dump.
SOURCE_DIR = './simple/articles'
# The output directory where the DOS-compatible archive will be built.
OUTPUT_DIR = './ENCYDOS'
# Set to 1 to include Category: pages, 0 to exclude them.
INCLUDE_CATEGORIES = 1 

# Namespaces to completely ignore during the build.
DROP_NAMESPACES = {'User', 'User_talk', 'Talk', 'Template', 'Template_talk', 
                   'Wikipedia', 'Wikipedia_talk', 'Image', 'Image_talk', 
                   'MediaWiki', 'MediaWiki_talk', 'Help', 'Help_talk', 
                   'Special', 'Transwiki', 'Utente', 'WP', 'WT', 'CAT'}
if INCLUDE_CATEGORIES == 0: 
    DROP_NAMESPACES.update({'Category', 'Category_talk'})

# --- CHARACTER ENCODING MAPS ---
# Maps Unicode characters to CP437/DOS-compatible HTML entities or ASCII fallbacks.
latin_to_entity = {chr(c): f"&{e};" for c, e in html.entities.codepoint2name.items()}
ascii_swaps = {
    '·': '-', '•': '*', '–': '-', '—': '-', '“': '"', '”': '"', 
    '‘': "'", '’': "'", '×': 'x', '°': '&deg;', '²': '^2', '³': '^3',
    '′': "'", '″': '"', '½': '1/2', '¼': '1/4', '¾': '3/4',
    '\u200b': '', '\u200c': '', '\u200d': '', '\ufeff': '', '\xa0': ' '
}

def clean_text(text):
    """Convert Unicode text to strict ASCII, using HTML entities where necessary."""
    new_text = []
    for char in text:
        if char in ascii_swaps: new_text.append(ascii_swaps[char])
        elif ord(char) < 128: new_text.append(char)
        elif char in latin_to_entity: new_text.append(latin_to_entity[char])
    return "".join(new_text)

def get_dos_name(title, original_filename):
    """
    Generate an 8.3 compliant filename. 
    Format: <4-char-prefix><4-char-hash>.htm (e.g., 'chob2a77.htm')
    """
    clean_title = re.sub(r'[^a-z0-9]', '', title.lower())
    prefix = (clean_title + "xxxx")[:4]
    match = re.search(r'_([0-9a-f]{4})\.html$', original_filename)
    hash_str = match.group(1) if match else hashlib.md5(title.encode('utf-8')).hexdigest()[:4]
    return f"{prefix}{hash_str}.htm"

def remove_matching_text_blocks(root, matcher, container_names):
    """
    Remove matching notice text and its nearest enclosing container.
    Ensures the DOM root is never accidentally destroyed (which causes BS4 crashes).
    """
    matches = list(root.find_all(string=matcher))
    for text_node in matches:
        parent = getattr(text_node, 'parent', None)
        if parent is None:
            continue # Already deleted by a previous match in this loop
        
        container = None
        # Walk up the tree, but stop before reaching the article root
        while parent is not None and parent is not root:
            if parent.name in container_names:
                container = parent
                break
            parent = parent.parent
            
        if container is not None:
            container.decompose()
        else:
            text_node.extract()

def make_nav_bar(current=None, prefix='', title=None):
    """
    Generate the standard grey top navigation bar.
    Note: Arachne adds forced margins between consecutive tables. To fix the 
    white gap at the top of articles, the title is appended as a second row 
    inside the nav bar table itself.
    """
    items = [
        ('home',     f'{prefix}index.htm',    'Home'),
        ('calendar', f'{prefix}calendar.htm', 'Calendar'),
        ('dice',     f'{prefix}dice.htm',     'Dice'),
        ('about',    f'{prefix}about.htm',    'About'),
        ('faq',      f'{prefix}faq.htm',      'FAQ'),
    ]
    rendered = []
    for key, href, label in items:
        if key == current:
            rendered.append(f'<b>{label}</b>')
        else:
            rendered.append(f"<a href='{href}'>{label}</a>")
            
    html = (
        "<table width='100%' cellpadding='3' cellspacing='0' border='0' bgcolor='#E6E6E6'>"
        "<tr><td bgcolor='#E6E6E6'><font size='2' face='Arial, Helvetica, sans-serif'>"
        + ' &nbsp; '.join(rendered) +
        "</font></td></tr>"
    )
    
    if title:
        html += f"<tr><td bgcolor='#FFFFFF'><font size='+2'><b>{title}</b></font></td></tr>"
    html += "</table>"
    
    # Add a clean line under the title
    if title:
        html += "<hr>"
        
    return html

def generate_docs():
    """Generate the static About, FAQ, and Home page documentation."""
    about_content = """
    <p><b>Welcome to ENCYDOS: The Offline Encyclopedia.</b></p>
    <p>This is a static preservation mirror of the Simple English Wikipedia, capturing the database exactly as it appeared in June 2008 (approximately 43,000 articles).</p>
    <p>ENCYDOS was created to fill a historical gap: providing a hyperlinked, encyclopedic reference work for native MS-DOS and 16-bit hardware. It is tested directly on the Arachne 1.70 browser.</p>
    <p><b>Project Goals:</b></p>
    <p>&bull; Preserve a snapshot of early wiki culture.</p>
    <p>&bull; Demonstrate the viability of hypertext on constrained hardware.</p>
    <p>&bull; Provide a functional, distraction-free reading experience.</p>
    <p><b>About the Name:</b><br>ENCYDOS (pronounced "En-sigh-dos") is a portmanteau of "Encyclopedia" and "DOS."</p>
    <p><b>Development Note:</b><br>The Python build pipeline used to sanitize this archive was developed via an AI-assisted collaboration, translating 2008 MediaWiki HTML into a format that strictly complies with Arachne's rendering limits.</p>
    <hr>
    <p align='center'><font size='1' color='#666666'>
    Copyright &copy; 2026 ByteFolium. Released under the 0BSD License.
    </font></p>
    """

    faq_content = """
    <p><b>Q: Why are there no images?</b><br>A: The original 2008 static HTML dump did not include the actual image binaries. All image tags, thumbnail containers, and orphaned captions were stripped to save space and prevent broken layout boxes.</p>
    <p><b>Q: Why are some characters missing or replaced?</b><br>A: The original Wikipedia used UTF-8. DOS browsers only understand standard ASCII and CP437. Western European accents were converted into HTML entities (like &deg;), while unrenderable languages (like Japanese) were stripped.</p>
    <p><b>Q: Why are the filenames so strange?</b><br>A: To comply with the FAT32/ISO9660 8.3 limit, every article is mapped to an 8-character filename. The alphabetical index handles the mapping.</p>
    <p><b>Q: How do I search?</b><br>A: DOS cannot run modern JavaScript search scripts. Use the analog <b>Dice Function</b> (available in the top nav bar) with two 6-sided dice to generate a letter, or click through the A-Z index manually.</p>
    <p><b>Q: Why are some links dead?</b><br>A: This mirror only includes "Main" and "Category" namespaces, so links to "User:" or "Talk:" pages were removed. Additionally, external web links are preserved exactly as they appeared in 2008, meaning many will point to sites that have since gone offline.</p>
    <p><b>Q: What is the license?</b><br>A: The text in this June 2008 snapshot predates the 2009 Wikimedia migration. It is available under the GNU Free Documentation License (GFDL) and additionally under CC BY-SA 3.0. See README.TXT for details.</p>
    """

    def build(title, current, content):
        return (
            f"<html><head><title>{title} - ENCYDOS</title></head><body bgcolor='#FFFFFF'>\n"
            "<a name='top'></a>\n"
            f"{make_nav_bar(current=current, title=title)}"
            f"{content}\n"
            "<hr>\n"
            "<p align='center'><font size='1' face='Arial, Helvetica, sans-serif'>"
            "<a href='index.htm'>[ Home ]</a>"
            "</font></p>\n"
            "</body></html>"
        )

    with open(os.path.join(OUTPUT_DIR, 'about.htm'), 'w', encoding='ascii') as f:
        f.write(build("About", 'about', about_content))
    with open(os.path.join(OUTPUT_DIR, 'faq.htm'), 'w', encoding='ascii') as f:
        f.write(build("FAQ", 'faq', faq_content))

def main():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(os.path.join(OUTPUT_DIR, 'art'), exist_ok=True)
    
    file_map = {}
    title_to_dos = {}
    empty_pages = set()
    
    # === PHASE 1: SCANNING & FILENAME MAPPING ===
    print("Phase 1: Scanning source files and mapping 8.3 filenames...")
    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            if not file.endswith('.html'): continue
            title = re.sub(r'(_[0-9a-f]{4})?\.html$', '', file).replace('~', ':')
            if title.split(':')[0] in DROP_NAMESPACES: continue
            
            # Drop read-only maintenance category pages entirely
            if title.startswith('Category:'):
                clean_title = title.replace('_', ' ')
                if re.search(r'(need to be|cleanup|stub|wikify|maintenance|articles with|complex)', clean_title, re.I):
                    continue
            
            dos_name = get_dos_name(title, file)
            letters = re.sub(r'[^a-z]', '', title.lower()) + "xxx"
            rel_dir = os.path.join('art', letters[0], letters[1], letters[2])
            
            orig_path = os.path.join(root, file)
            dos_path = os.path.join(rel_dir, dos_name)
            
            file_map[orig_path] = (dos_path, title)
            title_to_dos[title] = dos_path

    print(f"Mapped {len(file_map)} files.")

    # === PHASE 2: REDIRECT RESOLUTION ===
    print("Phase 2: Resolving redirects...")
    redirects = {}
    for orig_path, (dos_path, title) in file_map.items():
        if os.path.getsize(orig_path) < 1000:
            with open(orig_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                match = re.search(r'url=\.\./\.\./\.\./\.\./articles/[^"/]+/[^"/]+/[^"/]+/([^"]+\.html)', content) or re.search(r'href="\.\./\.\./\.\./\.\./articles/[^"/]+/[^"/]+/[^"/]+/([^"]+\.html)"', content)
                if match:
                    target_title = re.sub(r'(_[0-9a-f]{4})?\.html$', '', match.group(1)).replace('~', ':')
                    if target_title in title_to_dos:
                        redirects[title] = title_to_dos[target_title]

    # === PHASE 3: SANITIZATION & FORMATTING ===
    print("Phase 3: Sanitizing HTML and fixing layout for Arachne...")
    count = 0
    for orig_path, (dos_path, title) in file_map.items():
        with open(orig_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'lxml')

        # Extract page title
        h1 = soup.find('h1', class_='firstHeading')
        page_title = clean_text(h1.get_text(strip=True)) if h1 else clean_text(title)

        # Extract metadata (last modified and contributors)
        last_modified = ""
        credits_line = ""
        credits_li = soup.find('li', id='f-credits') or soup.find('li', id='f-lastmod')
        if credits_li:
            raw = clean_text(credits_li.get_text(strip=True))
            if ' by ' in raw:
                date_part, rest = raw.split(' by ', 1)
                last_modified = date_part.strip()
                if '. Based on work by ' in rest:
                    _, contributors_part = rest.split('. Based on work by ', 1)
                    contributors_part = contributors_part.strip()
                    contributors_part = re.sub(r'^Wikipedia user\(s\)\s*', '', contributors_part)
                    contributors_part = re.sub(r'\s+of the Simple English Wikipedia\.?$', '', contributors_part)
                    contributors_part = re.sub(r'\.$', '', contributors_part)
                    names = re.split(r',\s*|\s+and\s+', contributors_part)
                    names = [n.strip() for n in names if n.strip()]
                    if len(names) > 10:
                        credits_line = f"{', '.join(names[:10])} and {len(names) - 10} others"
                    else:
                        credits_line = ', '.join(names)
            else:
                last_modified = raw

        content_div = soup.find('div', id='bodyContent') or soup.find('div', id='content')
        if content_div:
            # Remove old MediaWiki skin elements
            for element_id in ('siteSub', 'jump-to-nav'):
                for node in list(content_div.find_all(id=element_id)):
                    node.decompose()
            # Remove empty subtitle containers (like "From Wikipedia, the free encyclopedia")
            for element_id in ('contentSub', 'contentSub2'):
                for node in list(content_div.find_all(id=element_id)):
                    if not node.get_text(" ", strip=True):
                        node.decompose()
        
        # Setup document shell
        nav_bar = make_nav_bar(prefix='../../../../', title=page_title)
        clean_html = f"<html><head><title>{page_title} - ENCYDOS</title></head><body bgcolor='#FFFFFF'><a name='top'></a>{nav_bar}"
        
        if content_div:
            # --- 1. MEDIA REMOVAL ---
            for tag in content_div.find_all(['script', 'style', 'link', 'img']): tag.decompose()
            # Strip ALL superscripts (citations, audio links, etc.)
            for sup in content_div.find_all('sup'):
                sup.decompose()

            # Strip empty spans and isolated commas that were used for formatting
            for span in content_div.find_all('span'):
                if not span.get_text(strip=True) or span.get_text(strip=True) == ',':
                    span.decompose()
            
            # Strip standard image captions
            for cap in content_div.find_all(['td', 'div'], class_=re.compile(r'(thumbcaption|image_caption|infobox-caption|infobox-image)')):
                cap.decompose()

            # Strip orphaned captions in infobox cells that used to hold images
            for td in content_div.find_all('td'):
                if td.find('a', class_='image') or td.find('a', title=re.compile(r'\.(jpg|png|gif|svg)$', re.I)):
                    for small in td.find_all('small'):
                        small.decompose()
                    for text_node in list(td.find_all(string=True)):
                        if re.match(r'^\s*(View|Map|Location|Image|Picture) of [A-Z]', str(text_node)):
                            text_node.extract()
            
            # Clean up empty "Location" headers left behind by removed maps
            for td in content_div.find_all(['td', 'th']):
                if td.get_text(strip=True) in ('Location', 'Map'):
                    tr = td.find_parent('tr')
                    if tr:
                        next_tr = tr.find_next_sibling('tr')
                        if next_tr and not next_tr.get_text(strip=True):
                            next_tr.decompose()
                            tr.decompose()
            
            # Clean up consecutive <br> tags left by removed images
            for br_tag in content_div.find_all('br'):
                if br_tag.get('clear'):
                    br_tag.decompose()
                if br_tag.next_sibling and br_tag.next_sibling.name == 'br':
                    br_tag.decompose()
                elif br_tag.previous_sibling and br_tag.previous_sibling.name == 'br':
                    br_tag.decompose()
                    
            for ambox in content_div.find_all(['table', 'div'], class_='ambox'):
                ambox.decompose()

            # Remove infobox media cells (posters, images, covers) and their captions
            for td in content_div.find_all('td'):
                if not hasattr(td, 'attrs') or td.attrs is None:
                    continue
                if td.get('colspan') == '2':
                    text = td.get_text(strip=True).lower()
                    if ('image:' in text or 
                        'poster' in text or 
                        'screenshot' in text or 
                        'dvd cover' in text or 
                        'movie poster' in text):
                        td.decompose()

            # --- 2. BOILERPLATE & MAINTENANCE REMOVAL ---
            for noart in content_div.find_all(['div', 'table'], class_='noarticletext'):
                noart.decompose()
            for noart_text in content_div.find_all(string=re.compile(r'Wikipedia does not yet have an article with this name')):
                parent = noart_text.find_parent(['div', 'table'])
                if parent: parent.decompose()

            for complex_text in content_div.find_all(string=re.compile(r'may not be easy for everybody to understand')):
                parent = complex_text.find_parent(['table', 'div'])
                if parent: parent.decompose()
            
            remove_matching_text_blocks(
                content_div, lambda t: t and "This short article" in t, ('div', 'table', 'p')
            )
            
            for stub_div in content_div.find_all(['div', 'table'], class_=re.compile(r'(notice|metadata|stub)')):
                if 'stub' in stub_div.get('class', []) or 'short article' in stub_div.get_text():
                    stub_div.decompose()

            remove_matching_text_blocks(
                content_div, re.compile(r'(scheduled or expected future events|This article or section)'), ('table', 'div')
            )
            remove_matching_text_blocks(
                content_div, re.compile(r'Wikimedia Commons has media related'), ('table', 'div')
            )
            remove_matching_text_blocks(
                content_div, re.compile(r'You\s+can\s+help(?:\s+Wikipedia)?\s+by'), ('div', 'table', 'p')
            )
            # Absolutely bulletproof spoiler removal (catches tags inside text)
            for container in content_div.find_all(['div', 'table', 'p']):
                if 'Spoiler warning' in container.get_text():
                    # Only decompose if it's a short notice, not a massive article
                    if len(container.get_text()) < 200:
                        container.decompose()

            # Handle stubs that wrap the "help" and "adding to it" links in multiple text nodes
            stub_candidates = []
            for container in list(content_div.find_all(['div', 'table', 'p'])):
                txt = container.get_text()
                if 'This section is a stub' in txt and 'adding to it' in txt:
                    stub_candidates.append(container)
            for cand in stub_candidates:
                if not any('This section is a stub' in c.get_text() for c in cand.find_all(['div', 'table', 'p'])):
                    if cand.parent is not None:
                        cand.decompose()

            for thumb in content_div.find_all(class_='thumb'): thumb.decompose()
            for comment in content_div.find_all(string=lambda text: isinstance(text, Comment)): comment.extract()
            for edit_link in content_div.find_all(class_=['editsection', 'mw-editsection']): edit_link.decompose()

            # --- 3. CALENDAR ARTICLE HANDLING ---
            day_match = re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)_(\d+)$', title)
            calendar_table = content_div.find('table', id='calendar')
            if calendar_table:
                is_day_article = bool(day_match) and 1 <= int(day_match.group(2)) <= 31
                if is_day_article:
                    month_name = day_match.group(1)
                    month_table = None
                    for inner_table in calendar_table.find_all('table'):
                        header = inner_table.find('th')
                        if header and month_name in header.get_text():
                            month_table = inner_table
                            break
                    day_links = []
                    if month_table:
                        for a in month_table.find_all('a'):
                            txt = a.get_text(strip=True)
                            if txt.isdigit() and 1 <= int(txt) <= 31:
                                day_links.append(a.extract())
                    calendar_table.decompose()
                    if day_links:
                        nav_table = soup.new_tag('table')
                        nav_table['border'] = '1'
                        nav_table['bordercolor'] = '#666666'
                        nav_table['bgcolor'] = '#E6E6E6'
                        nav_table['cellpadding'] = '3'
                        nav_table['cellspacing'] = '0'
                        
                        nav_tr = soup.new_tag('tr')
                        nav_td = soup.new_tag('td')
                        nav_td['bgcolor'] = '#E6E6E6'
                        
                        nav_font = soup.new_tag('font')
                        nav_font['color'] = '#000000'
                        nav_b = soup.new_tag('b')
                        nav_b.string = f'{month_name}: '
                        nav_font.append(nav_b)
                        
                        for i, link in enumerate(day_links):
                            nav_font.append(link)
                            if i < len(day_links) - 1:
                                nav_font.append(' ')
                                
                        nav_td.append(nav_font)
                        nav_tr.append(nav_td)
                        nav_table.append(nav_tr)
                        
                        site_sub = content_div.find('h3', id='siteSub')
                        if site_sub:
                            site_sub.insert_after(nav_table)
                            nav_table.insert_after(soup.new_tag('br'))
                        else:
                            content_div.insert(0, nav_table)
                            content_div.insert(1, soup.new_tag('br'))
                else:
                    calendar_table.decompose()

            # --- 4. ANCHOR INJECTION ---
            seen_anchors = set()
            for el in content_div.find_all(attrs={'id': True}):
                anchor_name = el.get('id')
                if not anchor_name or anchor_name in seen_anchors:
                    continue
                if el.name == 'a' and el.get('name') == anchor_name:
                    seen_anchors.add(anchor_name)
                    continue
                if anchor_name in ('toc', 'bodyContent', 'content', 'catlinks', 'globalWrapper'):
                    continue
                seen_anchors.add(anchor_name)
                anchor = soup.new_tag('a')
                anchor['name'] = anchor_name
                el.insert_before(anchor)

            # --- 5. HATNOTE & NOTICE STYLING ---
            for notice in content_div.find_all(['div', 'table', 'p'], class_=re.compile(r'(hatnote|dablink|rellink|notice)')):
                new_table = soup.new_tag('table')
                new_table['border'] = '1'
                new_table['bordercolor'] = '#666666'
                new_table['bgcolor'] = '#E6E6E6'
                new_table['cellpadding'] = '4'
                new_table['cellspacing'] = '0'
                
                tr = soup.new_tag('tr')
                td = soup.new_tag('td')
                td['bgcolor'] = '#E6E6E6'
                
                font_tag = soup.new_tag('font')
                font_tag['size'] = '2'
                font_tag['face'] = 'Arial, Helvetica, sans-serif'
                font_tag['color'] = '#000000'
                
                for child in list(notice.contents):
                    font_tag.append(child.extract())
                    
                td.append(font_tag)
                tr.append(td)
                new_table.append(tr)
                
                # Check parent to avoid invalid <table> inside <p> nesting
                if notice.parent.name in ('p', 'span', 'font'):
                    notice.unwrap()
                    content_div.insert(0, new_table)
                else:
                    notice.replace_with(new_table)

            # --- 6. TABLE HEADER & COLOR CONVERSION ---
            for th in content_div.find_all('th'):
                for a in th.find_all('a'): a.unwrap()
                th.name = 'td'
                
                font_tag = soup.new_tag('font')
                font_tag['color'] = '#FFFFFF'
                b = soup.new_tag('b')
                for child in list(th.contents):
                    b.append(child.extract())
                font_tag.append(b)
                th.append(font_tag)
                
                th['bgcolor'] = '#6463FE'
                
                style = th.get('style', '') or ''
                if 'text-align:center' in style.replace(' ', '') or 'text-align: center' in style:
                    th['align'] = 'center'
                elif 'text-align:right' in style.replace(' ', '') or 'text-align: right' in style:
                    th['align'] = 'right'

            # Unwrap offline coordinate links
            for a in content_div.find_all('a', href=re.compile(r'geohack|tools\.wikimedia')):
                a.unwrap()

            # --- COORDINATE HANDLING ---
            coords = content_div.find(id='coordinates') or content_div.find(class_='geo')
            if coords:
                coord_text = coords.get_text(strip=True)
                coord_text = re.sub(r'(?:Coordinates:\s*)+', '', coord_text, flags=re.I).strip()
                coord_text = re.sub(r'\s*/\s*', ' / ', coord_text)
                
                # Check if we are inside an Infobox cell (td/th)
                if coords.find_parent(['td', 'th']):
                    # Just replace the span with pure text. No new tables.
                    coords.replace_with(NavigableString(coord_text))
                else:
                    # Standalone coordinates: create the grey pod
                    new_table = soup.new_tag('table')
                    new_table['border'] = '1'
                    new_table['bordercolor'] = '#666666'
                    new_table['bgcolor'] = '#E6E6E6'
                    new_table['cellpadding'] = '4'
                    new_table['cellspacing'] = '0'
                    
                    tr = soup.new_tag('tr')
                    td = soup.new_tag('td')
                    td['bgcolor'] = '#E6E6E6'
                    
                    font_tag = soup.new_tag('font')
                    font_tag['size'] = '2'
                    font_tag['face'] = 'Arial, Helvetica, sans-serif'
                    font_tag['color'] = '#000000'
                    font_tag.string = f"Coordinates: {coord_text}"
                    
                    td.append(font_tag)
                    tr.append(td)
                    new_table.append(tr)
                    coords.replace_with(new_table)

            # Handle non-th headers with background colors
            for td in content_div.find_all('td'):
                style = td.get('style', '') or ''
                bgcolor = td.get('bgcolor', '') or ''
                has_header_bg = bool(
                    bgcolor.upper() in ('#6463FE', '#CCCCFF') or
                    re.search(r'background[^;]*:\s*#(?:6463FE|CCCCFF)', style, re.I)
                )
                if has_header_bg:
                    td['bgcolor'] = '#6463FE'
                    for a in td.find_all('a'): a.unwrap()
                    if not td.find('font', color='#FFFFFF'):
                        font_tag = soup.new_tag('font')
                        font_tag['color'] = '#FFFFFF'
                        for child in list(td.contents):
                            font_tag.append(child.extract())
                        td.append(font_tag)

            # Convert single-character category headers
            for td in content_div.find_all('td'):
                text = td.get_text(strip=True)
                if len(text) == 1 and text.isalpha() and td.find('a'):
                    td['bgcolor'] = '#6463FE'
                    for a in td.find_all('a'): a.unwrap()
                    if not td.find('font', color='#FFFFFF'):
                        font_tag = soup.new_tag('font')
                        font_tag['color'] = '#FFFFFF'
                        b = soup.new_tag('b')
                        for child in list(td.contents):
                            b.append(child.extract())
                        font_tag.append(b)
                        td.append(font_tag)

            # --- 7. CATEGORY LINKS BOX ---
            catlinks = content_div.find('div', id='catlinks')
            if catlinks:
                # Unwrap any nested divs/p tags so they don't break the grey table
                for p in catlinks.find_all(['div', 'p', 'span']):
                    p.unwrap()
                
                for hidden in catlinks.find_all(class_='mw-hidden-catlinks'):
                    hidden.decompose()
                for hidden_text in catlinks.find_all(string=re.compile(r'Hidden categor')):
                    hidden_text.extract()

                # Strip out the visible maintenance links, but keep real categories
                maintenance_regex = re.compile(r'(need to be|cleanup|stub|wikify|maintenance|articles with|complex)', re.I)
                for a in catlinks.find_all('a'):
                    if maintenance_regex.search(a.get_text()):
                        a.decompose()
                
                # Clean up pipes safely (keep one pipe, just fix the spacing)
                for text_node in list(catlinks.find_all(string=True)):
                    if isinstance(text_node, NavigableString):
                        s = str(text_node)
                        s = re.sub(r'\s*\|\s*', ' | ', s) # Normalize to " | "
                        s = re.sub(r'(\s*\|\s*)+', ' | ', s) # Collapse double pipes
                        if s != str(text_node):
                            text_node.replace_with(NavigableString(s))
                            
                new_table = soup.new_tag('table')
                new_table['border'] = '1'
                new_table['bordercolor'] = '#666666'
                new_table['bgcolor'] = '#E6E6E6'
                new_table['cellpadding'] = '4'
                new_table['cellspacing'] = '0'
                
                tr = soup.new_tag('tr')
                td = soup.new_tag('td')
                td['bgcolor'] = '#E6E6E6'
                
                font_tag = soup.new_tag('font')
                font_tag['size'] = '2'
                font_tag['face'] = 'Arial, Helvetica, sans-serif'
                font_tag['color'] = '#000000'
                
                for child in list(catlinks.contents):
                    font_tag.append(child.extract())
                    
                td.append(font_tag)
                tr.append(td)
                new_table.append(tr)
                catlinks.replace_with(new_table)

            # --- 8. NAVBOX REFORMATTING ---
            for navbox in content_div.find_all('table', class_='navbox'):
                for junk in navbox.find_all('a', title=re.compile(r'(View this template|Discussion about this template|You can edit this template)')):
                    junk.decompose()
                for span in navbox.find_all('span'):
                    if span.get_text(strip=True) in ('•', 'v', 'd', 'e', '·', '|'):
                        span.decompose()
                for noprint in navbox.find_all(class_='noprint'):
                    noprint.decompose()
                
                navbox['border'] = '1'
                navbox['bordercolor'] = '#666666'
                navbox['cellpadding'] = '4'
                navbox['cellspacing'] = '0'
                navbox['bgcolor'] = '#FFFFFF'
                if 'width' in navbox.attrs: del navbox['width']
                if 'style' in navbox.attrs: del navbox['style']
                for div in navbox.find_all('div'): div.unwrap()

                for td in navbox.find_all('td'):
                    if 'bgcolor' in td.attrs:
                        td['bgcolor'] = '#6463FE'
                        for font in td.find_all('font'):
                            font['color'] = '#FFFFFF'
                
                for td in navbox.find_all('td'):
                    if td.get('bgcolor') != '#6463FE':
                        td['bgcolor'] = '#FFFFFF'
                        if not td.find('font', color='#000000'):
                            font_tag = soup.new_tag('font')
                            font_tag['color'] = '#000000'
                            for child in list(td.contents):
                                font_tag.append(child.extract())
                            td.append(font_tag)

                rows = navbox.find_all('tr', recursive=False)
                if rows:
                    last_row = rows[-1]
                    cells = last_row.find_all('td', recursive=False)
                    if len(cells) == 1 and cells[0].get('colspan'):
                        link_count = len(cells[0].find_all('a'))
                        text = cells[0].get_text(strip=True)
                        if link_count == 1 and len(text) < 40:
                            last_row.decompose()

            # --- 9. TOC STYLING ---
            toc = content_div.find(id='toc')
            if toc:
                toc['border'] = '1'
                toc['bordercolor'] = '#666666'
                toc['bgcolor'] = '#E6E6E6'
                toc['cellpadding'] = '2'
                toc['cellspacing'] = '0'
                if 'width' in toc.attrs: del toc['width']
                for td in toc.find_all('td'):
                    td['bgcolor'] = '#E6E6E6'
                toctoggle = toc.find(class_='toctoggle')
                if toctoggle: toctoggle.decompose()
                for div in toc.find_all('div'): div.unwrap()

            # --- 10. ZEBRA STRIPES ---
            for table in content_div.find_all('table'):
                if table.get('id') == 'toc': continue
                if 'infobox' in (table.get('class') or []): continue
                if 'navbox' in (table.get('class') or []): continue
                data_rows = []
                for tr in table.find_all('tr'):
                    if tr.find_parent('table') is not table: continue
                    cells = tr.find_all(['td', 'th'], recursive=False)
                    if not cells: continue
                    if tr.get('bgcolor') == '#6463FE' or any(cell.get('bgcolor') == '#6463FE' for cell in cells): continue
                    data_rows.append(tr)
                
                if len(data_rows) < 4: continue
                for i, tr in enumerate(data_rows):
                    tr['bgcolor'] = '#DCDCDC' if i % 2 == 0 else '#FFFFFF'

            # --- 10b. PRESERVE LIST BULLETS ---
            for list_tag in content_div.find_all(['ul', 'ol']):
                # Skip the Table of Contents (it has its own numbering)
                if list_tag.find_parent(id='toc'):
                    continue
                    
                if list_tag.name == 'ol':
                    for i, li in enumerate(list_tag.find_all('li', recursive=False), 1):
                        li.insert(0, NavigableString(f'{i}. '))
                else:
                    for li in list_tag.find_all('li', recursive=False):
                        li.insert(0, NavigableString('* '))

            # --- 11. ATTRIBUTE & TEXT CLEANUP ---
            for tag in content_div.find_all(True):
                for child in tag.children:
                    if isinstance(child, str): child.replace_with(clean_text(child))
                
                new_attrs = {}
                if tag.name in ('table', 'td', 'th'):
                    if 'width' in tag.attrs: del tag.attrs['width']
                    if 'height' in tag.attrs: del tag.attrs['height']
                    if 'style' in tag.attrs:
                        new_style = re.sub(r'\b(?:width|height|float|clear|white-space)\s*:\s*[^;]+;?', '', tag['style'])
                        if new_style.strip(' ;'):
                            tag['style'] = new_style
                        else:
                            del tag['style']
                if tag.name == 'a':
                    if 'name' in tag.attrs: new_attrs['name'] = tag['name']
                    elif 'id' in tag.attrs: new_attrs['name'] = tag['id']
                
                if tag.name == 'font':
                    if 'color' in tag.attrs: new_attrs['color'] = tag['color']
                    if 'size' in tag.attrs: new_attrs['size'] = tag['size']
                    if 'face' in tag.attrs: new_attrs['face'] = tag['face']
                
                # Convert structural tags to DOS-friendly equivalents
                if tag.name in ('ul', 'ol', 'dl'): tag.name = 'div'
                if tag.name in ('li', 'dt', 'dd'): tag.name = 'p'
                if tag.name == 'pre': tag.name = 'p'
                
                bgcolor = tag.get('bgcolor')
                if not bgcolor and 'style' in tag.attrs:
                    match = re.search(r'background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6})', tag['style'])
                    if match: bgcolor = match.group(1)
                
                if bgcolor and tag.name in ('td', 'tr', 'table'):
                    new_attrs['bgcolor'] = bgcolor
                
                if 'href' in tag.attrs:
                    href = unquote(tag['href'])
                    href = re.sub(r'^http://simple\.wikipedia\.org\.\./\.\./\.\./\.\./', '../../../../', href)
                    
                    # Preserve the #section anchor
                    fragment = ""
                    if '#' in href:
                        href, fragment = href.split('#', 1)
                        fragment = '#' + fragment

                    match = re.search(r'articles/[^"]*?/([^"/]+\.html)', href)
                    if match:
                        link_title = re.sub(r'(_[0-9a-f]{4})?\.html$', '', match.group(1)).replace('~', ':')
                        if link_title in redirects: href = f"../../../../{redirects[link_title]}"
                        elif link_title in title_to_dos: href = f"../../../../{title_to_dos[link_title]}"
                        else: href = "#"
                    new_attrs['href'] = href + fragment
                
                if 'colspan' in tag.attrs: new_attrs['colspan'] = tag['colspan']
                if 'rowspan' in tag.attrs: new_attrs['rowspan'] = tag['rowspan']
                if 'align' in tag.attrs: new_attrs['align'] = tag['align']
                if 'valign' in tag.attrs: new_attrs['valign'] = tag['valign']

                tag.attrs = new_attrs
            
            # --- 12. TABLE DEFAULTS & EMPTY ROW REMOVAL ---
            for tr in content_div.find_all('tr'):
                cells = tr.find_all(['td', 'th'], recursive=False)
                if cells and all(not c.get_text(strip=True) and not c.find('a') and not c.find('table') for c in cells):
                    tr.decompose()
            
            for table in content_div.find_all('table'):
                if 'cellpadding' not in table.attrs: table['cellpadding'] = '2'
                if 'cellspacing' not in table.attrs: table['cellspacing'] = '0'
                if 'border' not in table.attrs: table['border'] = '1'
                if 'bordercolor' not in table.attrs: table['bordercolor'] = '#666666'
                if 'bgcolor' not in table.attrs: table['bgcolor'] = '#FFFFFF'
            
            for weird_tag in content_div.find_all(['template', 'svg', 'math']):
                weird_tag.decompose()

            # --- 13. ESCAPED MARKUP & LEAKED ATTRIBUTE STRIPPING ---
            garbage_wrappers = []
            for tag in content_div.find_all(['span', 'div']):
                html_repr = str(tag)
                if ('&lt;span class=' in html_repr or '&lt;div style=' in html_repr or '&lt;cite ' in html_repr):
                    garbage_wrappers.append(tag)
            for tag in garbage_wrappers:
                if tag.parent is not None: tag.decompose()

            for text_node in list(content_div.find_all(string=True)):
                if not isinstance(text_node, NavigableString): continue
                s = str(text_node)
                new_s = re.sub(r'^(?:\s*(?:colspan|rowspan|style|class|align|valign|width|height)="[^"]*")+', '', s)
                if new_s != s: text_node.replace_with(NavigableString(new_s))

            for text_node in list(content_div.find_all(string=True)):
                if not isinstance(text_node, NavigableString): continue
                s = str(text_node)
                if not re.match(r'\s*\{\|\s*class=', s): continue
                new_s = re.sub(r'\{\|.*?(?=\|\}|\Z)', '', s, flags=re.DOTALL)
                if new_s != s: text_node.replace_with(NavigableString(new_s))

            for text_node in list(content_div.find_all(string=True)):
                if not isinstance(text_node, NavigableString): continue
                s = str(text_node)
                new_s = re.sub(r'</?[a-zA-Z][^<>]{0,300}?>', '', s)
                new_s = re.sub(r'&lt;/?[a-zA-Z][^<>]{0,300}?&gt;', '', new_s)
                if new_s != s: text_node.replace_with(NavigableString(new_s))

            # --- 14. FINAL PRE-FLIGHT CLEANUP ---
            remove_matching_text_blocks(
                content_div, re.compile(r'(The title of this article is wrong|that this article is completely)'), ('div', 'table', 'p')
            )

            for child in list(content_div.children):
                if isinstance(child, NavigableString) and child.strip():
                    new_p = soup.new_tag('p')
                    new_p.append(child.extract())
                    content_div.append(new_p)

            for comment in content_div.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            # --- 15. EMPTY PAGE CHECK ---
            if not content_div.get_text(strip=True):
                empty_pages.add(title)
                empty_notice = soup.new_tag('p')
                empty_notice['align'] = 'center'
                empty_notice.string = "[ This article's content could not be converted for DOS. It likely consisted entirely of images or complex templates. ]"
                content_div.append(empty_notice)

            # === SERIALIZATION ===
            try:
                content_str = ''.join(str(c) for c in content_div.contents)
            except TypeError as exc:
                raise RuntimeError(
                    f"Serialization failed: {orig_path}; tag_name={content_div.name!r}; "
                    f"decomposed={getattr(content_div, 'decomposed', 'unknown')}"
                ) from exc

            # Normalize XHTML <br/> to <br> BEFORE whitespace cleanup
            content_str = re.sub(r'<br\s*/?>', '<br>', content_str, flags=re.I)

            # Post-serialization formatting fixes
            content_str = re.sub(r'</td>\s*<tr', '</td></tr><tr', content_str)
            content_str = re.sub(r'^(\s|<br>|<p>|</p>)+', '', content_str, flags=re.I)
            content_str = re.sub(r'<(p|div)>(\s|&nbsp;|<br>)*</\1>', '', content_str)
            content_str = re.sub(r'(<br>\s*){2,}', '<br>', content_str)
            content_str = re.sub(r'&amp;(#\d+|[a-zA-Z]+);', r'&\1;', content_str)
            content_str = content_str.replace('&sup1;', '^1').replace('&sup2;', '^2').replace('&sup3;', '^3')
            content_str = content_str.replace('&frac12;', '1/2').replace('&frac14;', '1/4').replace('&frac34;', '3/4')
            content_str = content_str.replace('&prime;', "'").replace('&Prime;', '"')
            content_str = content_str.replace('&ndash;', '-').replace('&mdash;', '-').replace('&middot;', '-')
            
            # Universal language template cleanup
            content_str = re.sub(r'\([^,)]+?:\s*,\s*([^)]+)\)', r'(\1)', content_str)
            content_str = re.sub(r'\(\s*,\s*([^)]+)\)', r'(\1)', content_str)
            content_str = re.sub(r'\([^,)]+?:\s*\)', '', content_str)
            content_str = re.sub(r'\(\s*\)', '', content_str)
            content_str = re.sub(r'\?\)', ')', content_str)
            
            clean_html += content_str
        
        # Footer / Bottom Nav
        clean_html += "\n<hr>\n"
        clean_html += (
            "<p align='center'><font size='1' face='Arial, Helvetica, sans-serif'>"
            "<a href='#top'>[ Back to Top ]</a> &nbsp; "
            "<a href='../../../../index.htm'>[ Home ]</a>"
            "</font></p>\n"
        )
        if last_modified:
            clean_html += f"<p align='center'><small>{last_modified}</small></p>\n"
        if credits_line:
            clean_html += (
                "<table border='1' bordercolor='#666666' bgcolor='#E6E6E6' cellpadding='4' cellspacing='0'><tr><td bgcolor='#E6E6E6'>"
                "<font size='2' face='Arial, Helvetica, sans-serif' color='#000000'>"
                f"<b>Contributors:</b> {credits_line}<br>"
                "<small>Text available under GFDL and CC BY-SA 3.0.</small>"
                "</font></td></tr></table>\n"
            )
        clean_html += "</body></html>"
        clean_html = clean_html.replace('<br/>', '<br>').replace('<br />', '<br>')

        # Write file
        out_path = os.path.join(OUTPUT_DIR, dos_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='ascii', errors='ignore') as f:
            f.write(clean_html)
            
        count += 1
        if count % 10000 == 0: print(f"  Sanitized {count} files...")

    # === PHASE 4: INDEX GENERATION ===
    print("Phase 4: Generating A-Z, Calendar, and Dice Indexes...")
    index_tree = defaultdict(lambda: defaultdict(list))
    for orig_path, (dos_path, title) in file_map.items():
        if title in empty_pages: 
            continue
        safe_title = clean_text(title)
        stripped = title
        while stripped:
            c = unicodedata.normalize('NFKD', stripped[0]).encode('ASCII', 'ignore').decode('ASCII')
            if c and c[0].isalnum():
                break
            stripped = stripped[1:]
        if not stripped: continue

        first_char = stripped[0]
        first_ascii = unicodedata.normalize('NFKD', first_char).encode('ASCII', 'ignore').decode('ASCII')
        if not first_ascii or not first_ascii[0].isalnum(): continue
        if first_ascii[0].isdigit(): first_ascii = '0-9'
        else: first_ascii = first_ascii[0].upper()

        first_two_raw = unicodedata.normalize('NFKD', stripped[:2]).encode('ASCII', 'ignore').decode('ASCII')
        if len(first_two_raw) >= 2 and first_two_raw[1].isalnum(): second = first_two_raw.capitalize()
        elif first_ascii == '0-9': second = '0-'
        else: second = first_ascii + '-'

        index_tree[first_ascii][second].append((safe_title, dos_path))

    letters = sorted([k for k in index_tree.keys() if len(k) == 1 or k == '0-9'])

    # 4b. Calendar Index
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    with open(os.path.join(OUTPUT_DIR, 'calendar.htm'), 'w', encoding='ascii') as f:
        f.write("<html><head><title>Calendar - ENCYDOS</title></head><body bgcolor='#FFFFFF'>")
        f.write("<a name='top'></a>")
        f.write(make_nav_bar(current='calendar'))
        f.write("<h1>Calendar Index (2008)</h1>")
        for m_idx, month in enumerate(months):
            f.write("<table border='1' bordercolor='#666666' bgcolor='#E6E6E6' cellpadding='4' cellspacing='0'><tr><td bgcolor='#E6E6E6'>")
            f.write(f"<font size='2' face='Arial, Helvetica, sans-serif' color='#000000'><b>{month}:</b> ")
            for d in range(1, days_in_month[m_idx] + 1):
                day_key = f"{month}_{d}"
                if day_key in title_to_dos:
                    f.write(f"<a href='{title_to_dos[day_key]}'>{d}</a> ")
                else:
                    f.write(f"{d} ")
            f.write("</font></td></tr></table><br>\n")
        f.write("<hr>")
        f.write("<p align='center'><font size='1' face='Arial, Helvetica, sans-serif'><a href='#top'>[ Back to Top ]</a> &nbsp; <a href='index.htm'>[ Home ]</a></font></p>")
        f.write("</body></html>")

    # 4c. Main Home Page
    with open(os.path.join(OUTPUT_DIR, 'index.htm'), 'w', encoding='ascii') as f:
        f.write("<html><head><title>Home - ENCYDOS</title></head><body bgcolor='#FFFFFF'>")
        f.write("<a name='top'></a>")
        f.write(make_nav_bar(current='home'))
        f.write("<h1>ENCYDOS</h1>")
        f.write("<h2><font color='#666666'>THE OFFLINE ENCYCLOPEDIA</font></h2>")
        f.write("<h3><font color='#666666'>Version 1.0</font></h3>")
        f.write("<hr>")
        f.write("<h3>Select a letter:</h3>")
        f.write("<table border='0' cellspacing='1' cellpadding='4' bgcolor='#000000' width='100%'>")
        for i in range(0, len(letters), 9):
            f.write("<tr>")
            for letter in letters[i:i+9]:
                f.write(f"<td bgcolor='#E6E6E6' align='center' width='11%'><font size='+1'><a href='idx_{letter}.htm'>[ {letter} ]</a></font></td>")
            f.write("</tr>")
        f.write("</table>")
        
        # Add the ByteFolium Publisher Mark
        f.write("<br><br><hr>")
        f.write("<p align='center'><font size='+1'><b>B Y T E F O L I U M</b></font><br>")
        f.write("<i>Preserving knowledge for legacy hardware.</i></p>")
        f.write("<p align='center'><font size='1' color='#666666'>ByteFolium Archive #001</font></p>")
        
        f.write("</body></html>")

    # 4d. Dice Function
    with open(os.path.join(OUTPUT_DIR, 'dice.htm'), 'w', encoding='ascii') as f:
        f.write("<html><head><title>Dice Function - ENCYDOS</title></head><body bgcolor='#FFFFFF'>")
        f.write("<a name='top'></a>")
        f.write(make_nav_bar(current='dice'))
        f.write("<h1>Dice Function (Analog Search)</h1>")
        f.write("<p>Because DOS cannot run modern JavaScript search engines, this archive uses an analog search method: rolling two standard 6-sided dice (2d6).</p>")
        
        f.write("<p><b>Step 1: Find your starting letter.</b><br>")
        f.write("Roll the dice. Your first die is the <b>ROW</b>, and your second die is the <b>COLUMN</b>. Find the square where they meet on the grid below and click it.</p>")
        
        grid = [
            ['A', 'B', 'C', 'D', 'E', 'F'],
            ['G', 'H', 'I', 'J', 'K', 'L'],
            ['M', 'N', 'O', 'P', 'Q', 'R'],
            ['S', 'T', 'U', 'V', 'W', 'X'],
            ['Y', 'Z', '0', '1', '2', '3'],
            ['4', '5', '6', '7', '8', '9']
        ]
        
        f.write("<table border='0' cellspacing='1' cellpadding='4' bgcolor='#000000' width='100%'>")
        f.write("<tr><td bgcolor='#FFFFFF'></td>")
        for col in range(1, 7):
            f.write(f"<td align='center' bgcolor='#6463FE'><font color='#FFFFFF'><b>Col {col}</b></font></td>")
        f.write("</tr>")
        
        for row_idx, row in enumerate(grid):
            f.write("<tr>")
            f.write(f"<td align='center' bgcolor='#6463FE'><font color='#FFFFFF'><b>Row {row_idx + 1}</b></font></td>")
            for cell in row:
                if cell:
                    if cell.isdigit(): link = "idx_0-9.htm"
                    else: link = f"idx_{cell}.htm"
                    f.write(f"<td align='center' bgcolor='#E6E6E6'><font size='+1'><a href='{link}'>[ {cell} ]</a></font></td>")
                else:
                    f.write("<td align='center' bgcolor='#E6E6E6'>&nbsp;</td>")
            f.write("</tr>")
            
        f.write("</table>")
        
        f.write("<p><b>Step 2: Pick your sub-category.</b><br>")
        f.write("Once you click a letter, you will see a list of two-letter combinations (like [ Ca ] or [ Ce ]). Because the number of combinations varies by letter, the dice cannot help you here. Simply browse the grid and click the combination that catches your eye.</p>")
        
        f.write("<p><b>Step 3: What if I land on a Number?</b><br>")
        f.write("If you land on a number, it will take you to the Number Index. Because standard 6-sided dice cannot roll a 0, 7, 8, or 9, the dice function ends here. Simply browse the Number Index manually to find your two-digit combination (e.g., [ 15 ] or [ 42 ]).</p>")
        
        f.write("<hr>")
        f.write("<p align='center'><font size='1' face='Arial, Helvetica, sans-serif'><a href='#top'>[ Back to Top ]</a> &nbsp; <a href='index.htm'>[ Home ]</a></font></p>")
        f.write("</body></html>")

    # 4e. Letter and Sub-Letter Indexes
    for letter, sub_dict in index_tree.items():
        if letter not in letters: continue 
        total_articles = sum(len(arts) for arts in sub_dict.values())
        
        with open(os.path.join(OUTPUT_DIR, f'idx_{letter}.htm'), 'w', encoding='ascii') as f:
            f.write(f"<html><head><title>Index {letter} - ENCYDOS</title></head><body bgcolor='#FFFFFF'>")
            f.write("<a name='top'></a>")
            f.write(make_nav_bar())
            f.write(f"<h1>Index: {letter}</h1>")

            if total_articles < 200:
                f.write("<table border='0' cellspacing='0' cellpadding='1' bgcolor='#000000' width='100%'><tr><td>")
                f.write("<table border='0' cellpadding='2' cellspacing='0' bgcolor='#FFFFFF' width='100%'>")
                all_arts = [art for arts in sub_dict.values() for art in arts]
                all_arts.sort()
                for i, (title_str, path) in enumerate(all_arts):
                    bg = "#DCDCDC" if i % 2 == 0 else "#FFFFFF" 
                    f.write(f"<tr bgcolor='{bg}'><td><a href='{path}'>{title_str}</a></td></tr>\n")
                f.write("</table></td></tr></table>")
                f.write("<hr>")
                f.write("<p align='center'><font size='1' face='Arial, Helvetica, sans-serif'><a href='#top'>[ Back to Top ]</a></font></p>")
            else:
                f.write("<h2>Select a two-letter combination:</h2>")
                subs = sorted(sub_dict.keys())
                subs = [s for s in subs if len(s) == 2 and all((c.isalnum() or c == '-') for c in s)]
                if letter == '0-9': subs = [s for s in subs if s[0].isdigit()]
                
                f.write("<table border='0' cellspacing='1' cellpadding='4' bgcolor='#000000' width='100%'>")
                for i in range(0, len(subs), 7):
                    f.write("<tr>")
                    for sub in subs[i:i+7]:
                        f.write(f"<td bgcolor='#E6E6E6' align='center' width='14%'><font size='+1'><a href='idx_{sub}.htm'>[ {sub} ]</a></font></td>")
                    
                    padding_needed = 7 - len(subs[i:i+7])
                    if padding_needed > 0:
                        for _ in range(padding_needed):
                            f.write("<td bgcolor='#E6E6E6'>&nbsp;</td>")
                    f.write("</tr>")
                f.write("</table>")
            f.write("</body></html>")

        # Sub-indexes that need pagination (e.g. "Ca")
        if total_articles >= 200:
            for sub, arts in sub_dict.items():
                if len(sub) != 2 or not all((c.isalnum() or c == '-') for c in sub): continue
                arts.sort()
                
                SUB_PAGE_SIZE = 800
                chunks = [arts[i:i+SUB_PAGE_SIZE] for i in range(0, len(arts), SUB_PAGE_SIZE)]
                page1_name = f'idx_{sub}.htm'
                
                for page_idx, chunk in enumerate(chunks, 1):
                    page_name = page1_name if page_idx == 1 else f'idx_{sub}_{page_idx}.htm'
                    with open(os.path.join(OUTPUT_DIR, page_name), 'w', encoding='ascii') as f:
                        f.write(f"<html><head><title>Index {sub} - ENCYDOS</title></head><body bgcolor='#FFFFFF'>")
                        f.write("<a name='top'></a>")
                        f.write(make_nav_bar())
                        f.write(f"<h1>Index: {sub}</h1>")
                        f.write(f"<p><font size='2' face='Arial, Helvetica, sans-serif'><a href='idx_{letter}.htm'>[ &lt; Back to {letter} ]</a></font></p>")
                        if len(chunks) > 1:
                            f.write("<p><font size='2' face='Arial, Helvetica, sans-serif'>")
                            f.write(f"Page {page_idx} of {len(chunks)} &mdash; ")
                            for i in range(1, len(chunks) + 1):
                                if i == page_idx:
                                    f.write(f"<b>[ {i} ]</b> ")
                                else:
                                    link = page1_name if i == 1 else f"idx_{sub}_{i}.htm"
                                    f.write(f"<a href='{link}'>[ {i} ]</a> ")
                            f.write("</font></p>")
                        
                        f.write("<table border='0' cellspacing='0' cellpadding='1' bgcolor='#000000' width='100%'><tr><td>")
                        f.write("<table border='0' cellpadding='2' cellspacing='0' bgcolor='#FFFFFF' width='100%'>")
                        for i, (title_str, path) in enumerate(chunk):
                            bg = "#DCDCDC" if i % 2 == 0 else "#FFFFFF"
                            f.write(f"<tr bgcolor='{bg}'><td><a href='{path}'>{title_str}</a></td></tr>\n")
                        f.write("</table></td></tr></table>")
                        f.write("<hr>")
                        f.write("<p align='center'><font size='1' face='Arial, Helvetica, sans-serif'>")
                        f.write("<a href='#top'>[ Back to Top ]</a> &nbsp; ")
                        f.write(f"<a href='idx_{letter}.htm'>[ Back to {letter} ]</a> &nbsp; ")
                        f.write("<a href='index.htm'>[ Home ]</a>")
                        f.write("</font></p>")
                        f.write("</body></html>")

    generate_docs()
    print("Done! The build is complete. Copy the ENCYDOS folder to DOS.")

if __name__ == '__main__': main()