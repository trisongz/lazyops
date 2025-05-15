from __future__ import annotations

"""
Formatting Helpers
"""

import re
import html
import datetime
import contextlib
from typing import List, Dict, Any, Union, Optional, Tuple

def build_dict_from_str(
    data: str,
    **kwargs
) -> Union[List[Any], Dict[str, Any]]:
    """
    Helper to build a dictionary from a string
    """
    import json
    if (data.startswith('[') and data.endswith(']')) or (data.startswith('{') and data.endswith('}')):
        return json.loads(data)
    return build_dict_from_list(data.split(','), **kwargs)


def build_dict_from_list(
    data: List[str],
    seperator: str = '=',
) -> Dict[str, Any]:
    """
    Builds a dictionary from a list of strings
    """
    import json
    return json.loads(str(dict([item.split(seperator) for item in data])))


def build_dict_from_query(
    query: str,
    **kwargs,
) -> Dict[str, Union[int, float, str, datetime.datetime, Any]]:
    """
    Builds a dictionary from a query
    """
    # Try to base decode it
    if not query.startswith('{') and not query.startswith('['):
        import base64
        query = base64.b64decode(query).decode('utf-8')
    data = build_dict_from_str(query, **kwargs)
    for k,v in data.items():
        if 'date' in k:
            with contextlib.suppress(Exception):
                from lzo.utils.helpers.dates import parse_datetime
                v = parse_datetime(v)
        data[k] = v
    return data


## Cleaning

html_re_pattern = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
alphanumeric_pattern = re.compile(r'[^a-zA-Z0-9]')
dba_pattern = re.compile(r'(.+?)(?:\s+d[/]b[/]a|[/]d[/]b[/]a|[/]dba|[/]DBA)(?:\s+(.+))?$')
url_pattern = re.compile(r'(https?://\S+)')
name_pattern_regex = re.compile(r'(?:(?<=^)|(?<=[^A-Za-z.,]))[A-Za-z.,]+(?: [A-Za-z.,]+)*(?:(?=[^A-Za-z.,])|(?=$))')
underscore_pattern = re.compile("___+")

def clean_html(text: str) -> str:
    """
    Clean HTML
    """
    return html_re_pattern.sub('', html.unescape(text))


def cleanup_dots(text: str) -> str:
    """
    Cleans up the dots found in table of contents

    INTRODUCTION............................................ > INTRODUCTION.
    """
    return re.sub(r'\.+', '.', text).strip()

def extract_urls(text: str) -> List[str]:
    """
    Extracts urls from a string
    """
    return url_pattern.findall(text)

def cleanup_whitespace(text: str) -> str:
    """
    Cleans up the whitespace
    """
    return re.sub(r'\s+', ' ', text).strip()

def format_for_id(text: str, sep: str = '-') -> str:
    """
    Formats the text for an ID
    """
    return re.sub(r'\W+', sep, text).strip(sep).lower()


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

def extract_name(text: str) -> Optional[str]:
    """
    Extracts the name
    """
    text = text.replace('Contact', '').replace('at', '').strip()
    match = name_pattern_regex.search(text)
    return match[0] if match else None
    
def title_case_text(text: str) -> str:
    """
    Title cases the text
    """
    return ' '.join([word.capitalize() for word in text.split(' ')])

def unescape_html(text: str, replace_breaks: Optional[bool] = True) -> str:
    """
    Unescape HTML
    -> Kimberlie J. Laing, Grant Analyst, 301-903-3026&lt;br/&gt;kim.laing@science.doe.gov&lt;br/&gt;Catherine M. Ronning, Program Manager, 301-903-9549&lt;br/&gt;Catherine.Ronning@science.doe.gov&lt;br/&gt;'
    -> Kimberlie J. Laing, Grant Analyst, 301-903-3026<br/>kim.laing@science.doe.gov<br/>Catherine M. Ronning, Program Manager, 301-903-9549<br/>Catherine.Ronning@science.doe.gov<br/>
    """
    text = text.replace('�', ' ')
    text = html.unescape(text)
    if replace_breaks: text = text.replace('<br/>', '\n')
    return text.strip()


def normalize_sql_text(text: Optional[str]) -> Optional[str]:
    """
    Normalizes the text to be indexed/queried
    """
    if text is None or not text.strip(): return None
    return alphanumeric_pattern.sub(' ', text).replace('  ', ' ').replace('  ', ' ').strip()


def strip_or_none(text: str) -> Optional[str]:
    """
    Strips the text or returns None
    """
    return text.strip() or None

def extract_dba_and_company_name(company_name: str) -> Tuple[str, str]:
    # sourcery skip: extract-method
    """
    Extracts the DBA from the company name

    Examples:
        - SafeFlights Inc /D/B/A 14bis Supply Tracking -> [SafeFlights Inc, 14bis Supply Tracking]
        - compact power inc of america d/b/a Lightening Energy -> [compact power inc of america, Lightening Energy]
        - TaskUnite Inc (dba AMPAworks) -> [TaskUnite Inc, AMPAworks]
        - Systems And Processes Engineering Corporation (SPEC) -> [Systems And Processes Engineering Corporation, SPEC]
        - FitChimp Inc (DBA FitRankings) -> [FitChimp Inc, FitRankings]
        - (ES3) Engineering AND Software System Solution Inc -> [ES3, Engineering AND Software System Solution Inc]
        - Opto-Knowledge Systems Inc (OKSI) -> [Opto-Knowledge Systems Inc, OKSI]
        - Protonex LLC dba PNI Sensor -> [Protonex LLC, PNI Sensor]
        - AIR REFUELING TANKER TRANSPORT (ART2) LLC -> [AIR REFUELING TANKER TRANSPORT, ART2]
    """

    # Use re.match to find the pattern in the company name
    match = dba_pattern.match(company_name, re.IGNORECASE)
    if match:
        # Extract the Dba and company name parts
        dba = match.group(1).strip()
        company = match.group(2).strip() if match.group(2) else None
        if company and '(' in company: company = company[:company.find('(')-1].strip()
        return [strip_or_none(dba), strip_or_none(company)]

    i_start, i_end = company_name.find('('), company_name.find(')')
    if i_start != -1 and i_end != -1:
        dba = company_name[i_start+1:i_end].replace('dba', '').replace('DBA', '').strip()
        company = company_name.replace(dba, '').replace('(', '').replace(')', '').replace('dba', '').replace('DBA', '').replace('  ', ' ').strip()
        return [strip_or_none(dba), strip_or_none(company)]

    if 'dba' in company_name:
        parts = company_name.split('dba')
        return [strip_or_none(parts[1]), strip_or_none(parts[0])]
    
    return [company_name.strip(), None]


def count_non_sequential_integers(input_string: str) -> int:
    """
    Determine the number of non-sequential integers in a given string.
    
    Args:
        input_string (str): The input string to be analyzed.
        
    Returns:
        int: The number of non-sequential integers in the input string.
    """
    # Find all integers in the input string
    integers = [int(x) for x in re.findall(r'\d+', input_string)]
    return sum(integers[i] != integers[i - 1] + 1 for i in range(1, len(integers)))


def is_spam_domain(domain: str) -> bool:
    """
    Identify if a given domain is likely a spam domain.
    """
    if len(domain) > 50: return True
    if domain.count('i') > 4 and domain.count('a') > 4: return True
    if (
        domain.count('x') > 2 or 
        domain.count('z') > 2 or 
        domain.count('j') > 3 or 
        domain.count('w') > 3 or 
        domain.count('y') > 3 or 
        domain.count('f') > 3
    ): return True

    # Test Combinations
    if domain.count('x') > 1 and (domain.count('j') > 1 or domain.count('y') > 1): return True
    if domain.count('j') > 1 and domain.count('d') > 1 and domain.count('a') > 1: return True
    
    # Test for non-sequential integers
    n_non_seq = count_non_sequential_integers(domain)
    # if n_non_seq > 1:  return True
    return n_non_seq > 1
    

def reformat_spacing(text: str) -> str:
    """
    Reformat the spacing
    """
    text = text.replace('\n[', '\n\n**').replace(']:', ':**').replace('[', '**')
    text = text.replace('\n  - ', '\n\n  - ').replace('\n- ', '\n\n- ')
    return text.strip()

def parse_duration(duration: str) -> float:
    """
    Parses the duration

    5 minutes, 49.75 seconds -> 349.75
    """
    total = 0.0
    parts = duration.split(', ')
    for part in parts:
        if ' seconds' in part: total += float(part.split(' ')[0])
        elif ' minutes' in part: total += float(part.split(' ')[0]) * 60
        elif ' hours' in part: total += float(part.split(' ')[0]) * 3600
        elif ' days' in part: total += float(part.split(' ')[0]) * 86400
    return total


def combine_parts(*parts: Optional[str], sep: Optional[str] = '.') -> str:
    """
    Combines the parts into a single string
    """
    return sep.join(p for p in parts if p)


def clean_text(text: str) -> str:
    """
    Cleans the text
    """
    if '�' in text: text = text.replace('�', '')
    
    # Find and remove double underscores
    if underscore_pattern.search(text):
        text = underscore_pattern.sub(' ', text)
    
    # Cleanup HTML
    if '<' in text and '>' in text: 
        with contextlib.suppress(Exception):
            from markdownify import markdownify
            text = markdownify(text)
    
    return cleanup_whitespace(text)