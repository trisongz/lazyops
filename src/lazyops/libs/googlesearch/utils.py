
import os
import gzip
import random
import pathlib
import datetime
import contextlib
from http.cookiejar import LWPCookieJar
from urllib.parse import urlparse, parse_qs
from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from http.cookiejar import CookieJar



lib_path = pathlib.Path(__file__).parent.absolute()

home_folder = os.getenv('HOME', os.getenv('USERHOME'))

# Default user agent, unless instructed by the user to change it.
USER_AGENT = 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0)'


# Load the list of valid user agents from the install folder.
# The search order is:
#   * user_agents.txt.gz
#   * user_agents.txt
#   * default user agent

_user_agents: List[str] = None
_cookie_jar: LWPCookieJar = None

def load_cookie_jar() -> LWPCookieJar:
    """
    Load the cookie jar
    """
    global _cookie_jar
    if _cookie_jar is None:
        _cookie_jar = LWPCookieJar(
            os.path.join(
                home_folder or lib_path.as_posix(), 
                '.google-cookie'
            )
        )

        with contextlib.suppress(Exception):
            _cookie_jar.load()
    
    return _cookie_jar

def load_user_agents():
    """
    Loads the user agents from the user agents file.
    """
    global _user_agents
    if _user_agents is None:
        user_agents_file = lib_path.joinpath('user_agents.txt.gz')
        fp = gzip.open(user_agents_file.as_posix(), 'rb')
        try:
            _user_agents = [_.decode().strip() for _ in fp.readlines()]
        except Exception as e:
            _user_agents = [USER_AGENT]
        finally:
            fp.close()
    
    return _user_agents

def get_random_jitter(
    min_seconds: int = 2, 
    max_seconds: int = 5
) -> int:
    """
    Gets a random jitter
    """
    return random.randint(min_seconds, max_seconds)


# Get a random user agent.
def get_random_user_agent():
    """
    Get a random user agent string.

    :rtype: str
    :return: Random user agent string.
    """
    return random.choice(load_user_agents())



# Helper function to format the tbs parameter.
def get_tbs(from_date: datetime.datetime, to_date: datetime.datetime) -> str:
    """
    Helper function to format the tbs parameter.

    :param datetime.date from_date: Python date object.
    :param datetime.date to_date: Python date object.

    :rtype: str
    :return: Dates encoded in tbs format.
    """
    from_date = from_date.strftime('%m/%d/%Y')
    to_date = to_date.strftime('%m/%d/%Y')
    return f'cdr:1,cd_min:{from_date},cd_max:{to_date}'


# Filter links found in the Google result pages HTML code.
# Returns None if the link doesn't yield a valid result.
def filter_result(link: str) -> Optional[str]:
    """
    Filter links found in the Google result pages HTML code.
    """
    with contextlib.suppress(Exception):
        # Decode hidden URLs.
        if link.startswith('/url?'):
            o = urlparse(link, 'http')
            link = parse_qs(o.query)['q'][0]

        # Valid results are absolute URLs not pointing to a Google domain,
        # like images.google.com or googleusercontent.com for example.
        # TODO this could be improved!
        o = urlparse(link, 'http')
        if o.netloc and 'google' not in o.netloc:
            return link
    
    return None
