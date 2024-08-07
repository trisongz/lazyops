import re
from typing import Optional

alphanumeric_pattern = re.compile(r'[^a-zA-Z0-9]')

def normalize_sql_text(text: Optional[str]) -> Optional[str]:
    """
    Normalizes the text to be indexed/queried
    """
    if text is None or not text.strip(): return None
    return alphanumeric_pattern.sub(' ', text).replace('  ', ' ').replace('  ', ' ').strip()
