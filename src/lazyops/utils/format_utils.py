import re
import html
import contextlib
from typing import Optional

html_re_pattern = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
underscores = re.compile("___+")
name_pattern_regex = re.compile(r'(?:(?<=^)|(?<=[^A-Za-z.,]))[A-Za-z.,]+(?: [A-Za-z.,]+)*(?:(?=[^A-Za-z.,])|(?=$))')


def cleanup_whitespace(text: str) -> str:
    """
    Cleans up the whitespace
    """
    return re.sub(r'\s+', ' ', text).strip()

def cleanup_dots(text: str) -> str:
    """
    Cleans up the dots found in table of contents

    INTRODUCTION............................................ > INTRODUCTION.
    """
    return re.sub(r'\.+', '.', text).strip()


def extract_email(text: str) -> Optional[str]:
    """
    Extracts the email
    """
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match[0] if match else None


def extract_phone(text: str) -> Optional[str]:
    """
    Extracts the phone
    """
    # 205460001
    # 3014430995
    match = re.search(r'[\d\(\)\-]+', text)
    if not match: return None
    pn = match[0]
    if len(pn.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')) <= 9: return None
    return pn


def unescape_html(text: str, replace_breaks: Optional[bool] = True) -> str:
    """
    Unescape HTML
    """
    text = html.unescape(text)
    if replace_breaks: text = text.replace('<br/>', '\n')
    return text.strip()


def clean_html(text: str) -> str:
    """
    Clean HTML
    """
    return html_re_pattern.sub('', html.unescape(text))


def clean_text(text: str) -> str:
    """
    Cleans the text
    """
    if '�' in text: text = text.replace('�', '')
    
    # Find and remove double underscores
    if underscores.search(text):
        text = underscores.sub(' ', text)
    
    # Cleanup HTML
    if '<' in text and '>' in text: 
        with contextlib.suppress(Exception):
            from markdownify import markdownify
            text = markdownify(text)
            # text = cleanup_whitespace(text)
    
    return cleanup_whitespace(text)
    # return text