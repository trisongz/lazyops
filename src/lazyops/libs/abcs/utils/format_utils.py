
import re
import html
import json
import datetime
import contextlib
import base64
from typing import Optional, Dict, Any, List, Union, Tuple


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

def title_case_text(text: str) -> str:
    """
    Title cases the text
    """
    return ' '.join([word.capitalize() for word in text.split(' ')])

def unescape_html(text: str, replace_breaks: Optional[bool] = True) -> str:
    """
    Unescape HTML
    """
    text = text.replace('�', ' ')
    text = html.unescape(text)
    if replace_breaks: text = text.replace('<br/>', '\n')
    return text.strip()


html_re_pattern = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')

def clean_html(text: str) -> str:
    """
    Clean HTML
    """
    return html_re_pattern.sub('', html.unescape(text))


def build_dict_from_str(
    data: str,
    **kwargs
) -> Union[List[Any], Dict[str, Any]]:
    """
    Helper to build a dictionary from a string
    """
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
        query = base64.b64decode(query).decode('utf-8')
    data = build_dict_from_str(query, **kwargs)
    for k,v in data.items():
        if 'date' in k:
            with contextlib.suppress(Exception):
                v = parse_datetime(v)
        data[k] = v
    return data



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
    
    # We won't test for alphanumeric ratio because it's not very reliable
    # logger.info(f'Non-Sequential: {n_non_seq}', prefix = domain)
    # n_numeric = sum(c.isdigit() for c in domain)
    # n_alpha = sum(c.isalpha() for c in domain)
    # numeric_ratio = n_numeric / len(domain)
    # if numeric_ratio > 0.1: return True
    # # alpha_ratio = n_alpha / len(domain)
    # return False

def is_invalid_domain_filter(key: str, key_type: Optional[str] = None) -> bool:
    """
    Checks if the domain is spam for kvdb filtering
    """
    return False if key_type != 'hash_item' else is_spam_domain(key) 


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
