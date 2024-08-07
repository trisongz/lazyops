"""
Modified version of 
`googlesearch` by https://github.com/MarioVilas/googlesearch
"""


import abc
import time
import random
import asyncio
import contextlib
from pydantic import BaseModel
from lazyops.imports._aiohttpx import resolve_aiohttpx
from lazyops.imports._bs4 import resolve_bs4
from urllib.parse import quote_plus


resolve_aiohttpx(True)
resolve_bs4(True)

import aiohttpx
from bs4 import BeautifulSoup, Tag
from .utils import filter_result, load_user_agents, load_cookie_jar, get_random_jitter
from typing import List, Optional, Dict, Any, Union, Tuple, Set, Callable, Awaitable, TypeVar, Generator, AsyncGenerator



# URL templates to make Google searches.
url_parameters = (
    'hl', 'q', 'num', 'btnG', 'start', 'tbs', 'safe', 'cr', 'filter'
)

# RT = TypeVar('RT', str, Tuple[str, str])
RT = Union[str, Tuple[str, str], Tuple[str, str, str]]

class SearchParams(BaseModel):
    """
    The search params
    """
    query: str
    tld: Optional[str] = 'com'
    lang: Optional[str] = 'en' 
    tbs: Optional[str] = '0'
    safe: Optional[str] = 'off'
    num: Optional[int] = 10
    start: Optional[int] = 0
    stop: Optional[int] = None
    # pause: Optional[float] = 2.0
    country: Optional[str] = ''
    include_title: Optional[bool] = False
    include_description: Optional[bool] = False
    # extra_params: Optional[Dict[str,str]] = None

    @property
    def url_home(self) -> str:
        """
        Gets the home url
        """
        return f"https://www.google.{self.tld}/"
    
    @property
    def url_search(self) -> str:
        """
        Gets the search url
        """
        return f"https://www.google.{self.tld}/search?lr=lang_{self.lang}&" \
             f"q={self.query}&btnG=Google+Search&tbs={self.tbs}&safe={self.safe}&" \
             f"cr={self.country}&filter=0"
    
    @property
    def url_next_page(self) -> str:
        """
        Gets the next page url
        """
        return f"https://www.google.{self.tld}/search?lr=lang_{self.lang}&" \
                f"q={self.query}&start={self.start}&tbs={self.tbs}&safe={self.safe}&" \
                f"cr={self.country}&filter=0"
    
    @property
    def url_search_num(self) -> str:
        """
        Gets the search url
        """
        return f"https://www.google.{self.tld}/search?lr=lang_{self.lang}&" \
                 f"q={self.query}&num={self.num}&btnG=Google+Search&tbs={self.tbs}&" \
                 f"&safe={self.safe}scr={self.country}&filter=0"
    
    @property
    def url_next_page_num(self) -> str:
        """
        Gets the next page url
        """
        return f"https://www.google.{self.tld}/search?lr=lang_{self.lang}&" \
                    f"q={self.query}&num={self.num}&start={self.start}&tbs={self.tbs}&" \
                    f"safe={self.safe}&cr={self.country}&filter=0"
    
    @property
    def start_url(self) -> str:
        """
        Gets the start url
        """
        if self.start:
            return self.url_next_page if self.num == 10 else self.url_next_page_num
        return self.url_search if self.num == 10 else self.url_search_num
    
    def get_next_url(self) -> str:
        """
        Gets the next url
        """
        self.start += self.num
        return self.url_next_page if self.num == 10 else self.url_next_page_num
    
    def is_valid_link(self, anchor: Tag, hashes: Set) -> Optional[str]:
        """
        Validates the link
        """
        try:
            link = anchor['href']
        except KeyError:
            return None

        # Filter invalid links and links pointing to Google itself.
        link = filter_result(link)
        if not link: return None

        # Discard repeated results.
        h = hash(link)
        if h in hashes: return None
        hashes.add(h)
        return link
    
    def extract_result(self, anchor: Tag, desc: Tag, hashes: Set) -> Optional[RT]:
        """
        Extracts the result
        """
        link = self.is_valid_link(anchor, hashes)
        if not link: return None
        if self.include_title and self.include_description:
            return (link, anchor.text, desc.text)
        if self.include_description:
            return (link, desc.text)
        return (link, anchor.text) if self.include_title else link
    


class GoogleSearchClient(abc.ABC):

    def __init__(
        self,
        proxy: Optional[str] = None,
        user_agents: Optional[List[str]] = None,
        verify_ssl: Optional[bool] = True,
        default_lang: Optional[str] = 'en',
        timeout: Optional[int] = 10,
        max_connections: Optional[int] = 100,
        raise_exceptions: Optional[bool] = True,
        **kwargs,
    ):
        """
        Initializes the client
        """
        self.pre_init(**kwargs)
        self.proxy = proxy
        self.user_agents = user_agents or load_user_agents()
        self.verify_ssl = verify_ssl
        self.lang = default_lang
        self.raise_exceptions = raise_exceptions
        self.cookie_jar = load_cookie_jar()
        self.cookies = aiohttpx.Cookies(self.cookie_jar)
        self.timeout = timeout
        self.max_connections = max_connections
        self.api: aiohttpx.Client = None
        self.init_api(**kwargs)
        self.post_init(**kwargs)

    def pre_init(self, **kwargs):
        """
        Pre init
        """
        pass

    def post_init(self, **kwargs):
        """
        Post init
        """
        pass

    def init_api(self, **kwargs):
        """
        Initializes the api
        """
        if self.api is None:
            self.api = aiohttpx.Client(
                timeout = self.timeout,
                cookies = self.cookies,
                limits = aiohttpx.Limits(max_connections = self.max_connections),
                proxies = {"all://": self.proxy} if self.proxy else None,
                follow_redirects = True,
            )

    
    def _get_page(
        self,
        url: str,
        user_agent: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """
        Gets the page
        """
        user_agent = user_agent or random.choice(self.user_agents)
        request = self.api.build_request(
            "GET", 
            url, 
        )
        request.headers['User-Agent'] = user_agent
        response = self.api.send(request)
        if self.raise_exceptions: response.raise_for_status()
        self.cookies.extract_cookies(response)
        html = response.read()
        response.close()
        with contextlib.suppress(Exception):
            self.cookies.jar.save()
        return html
    
    def get_page(
        self,
        url: str,
        user_agent: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """
        Gets the page

        This is a wrapper that allows you to customize the 
        underlying logic of the get_page method
        """
        return self._get_page(url, user_agent, **kwargs)
    
    async def _aget_page(
        self,
        url: str,
        user_agent: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """
        Gets the page
        """
        user_agent = user_agent or random.choice(self.user_agents)
        request = await self.api.async_build_request(
            "GET", 
            url, 
        )
        request.headers['User-Agent'] = user_agent
        response = await self.api.async_send(request)
        if self.raise_exceptions: response.raise_for_status()
        self.cookies.extract_cookies(response)
        html = response.read()
        await response.aclose()
        with contextlib.suppress(Exception):
            self.cookies.jar.save()
        return html
    
    async def aget_page(
        self,
        url: str,
        user_agent: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """
        Gets the page

        This is a wrapper that allows you to customize the 
        underlying logic of the get_page method
        """
        return await self._aget_page(url, user_agent, **kwargs)
    

    
    def append_extra_params(
        self,
        url: str,
        extra_params: Dict[str, str],
    ) -> str:
        """
        Appends extra params
        """
        if not extra_params: return url
        for k, v in extra_params.items():
            k = quote_plus(k)
            v = quote_plus(v)
            url = f'{url}&{k}={v}'
        return url
    
    def extract_anchors(
        self,
        html: Union[str, bytes, BeautifulSoup],
    ) -> List[Tag]:
        """
        Extracts the anchors
        """
        soup = BeautifulSoup(html, 'html.parser') if isinstance(html, (bytes, str)) else html
        try:
            return soup.find(id='search').findAll('a')
            # Sometimes (depending on the User-agent) there is
            # no id "search" in html response...
        except AttributeError:
            # Remove links of the top bar.
            gbar = soup.find(id='gbar')
            if gbar: gbar.clear()
            return soup.findAll('a')
        
    def extract_description(
        self,
        html: Union[str, bytes, BeautifulSoup],
    ) -> List[Tag]:
        """
        Extracts the description
        """
        soup = BeautifulSoup(html, 'html.parser') if isinstance(html, (bytes, str)) else html
        try:
            return soup.find(id='search').findAll('span')
        except AttributeError:
            # Remove links of the top bar.
            gbar = soup.find(id='gbar')
            if gbar: gbar.clear()
            return soup.findAll('span')
    
    def validate_extra_params(
        self,
        extra_params: Dict[str, str],
    ):
        """
        Validates the extra params
        """
        for builtin_param in url_parameters:
            if builtin_param in extra_params:
                raise ValueError(
                    'GET parameter "%s" is overlapping with \
                    the built-in GET parameter',
                    builtin_param
                )
    
    def _search(
        self,
        query: str, 
        tld: Optional[str] = 'com', 
        lang: Optional[str] = 'en', 
        tbs: Optional[str] = '0', 
        safe: Optional[str] = 'off', 
        num: Optional[int] = 10, 
        start: Optional[int] = 0,
        stop: Optional[int] = None, 
        pause: Optional[float] = 2.0, 
        country: Optional[str] = '', 
        include_title: Optional[bool] = False,
        include_description: Optional[bool] = False,
        extra_params: Optional[Dict[str,str]] = None,
        user_agent: Optional[str] = None, 
        verify_ssl: Optional[bool] = True,
        **kwargs,
    ) -> Generator[RT, None, None]:  # sourcery skip: low-code-quality
        """
        Searches the query
        """
        hashes = set()

        # Count the number of links yielded.
        count = 0

        # Prepare the search string.
        query = quote_plus(query)

        # If no extra_params is given, create an empty dictionary.
        # We should avoid using an empty dictionary as a default value
        # in a function parameter in Python.
        if not extra_params: extra_params = {}
        if extra_params: self.validate_extra_params(extra_params)

        sp = SearchParams(
            query = query,
            tld = tld,
            lang = lang,
            tbs = tbs,
            safe = safe,
            num = num,
            start = start,
            stop = stop,
            country = country,
            include_title = include_title,
            include_description = include_description,
        )

        # Grab the cookie from the home page.
        self.get_page(sp.url_home, user_agent, **kwargs)

        url = sp.start_url

        # Loop until we reach the maximum result, if any (otherwise, loop forever).
        while not sp.stop or count < sp.stop:

            # Remember last count to detect the end of results.
            last_count = count

            # Append extra GET parameters to the URL.
            # This is done on every iteration because we're
            # rebuilding the entire URL at the end of this loop.
            url = self.append_extra_params(url, extra_params)

            # Sleep between requests.
            # Keeps Google from banning you for making too many requests.
            time.sleep(get_random_jitter(pause))

            # Request the Google Search results page.
            html = self.get_page(url, user_agent)
            soup = BeautifulSoup(html, 'html.parser')

            # Parse the response and get every anchored URL.
            anchors = self.extract_anchors(soup)
            desc_anchors = self.extract_description(soup)

            # Process every anchored URL.
            for (a, desc) in zip(anchors, desc_anchors):
                result = sp.extract_result(a, desc, hashes)
                if not result: continue

                # Yield the result.
                yield result

                # Increase the results counter.
                # If we reached the limit, stop.
                count += 1
                if sp.stop and count >= sp.stop:
                    return

            # End if there are no more results.
            # XXX TODO review this logic, not sure if this is still true!
            if last_count == count:
                break

            # Prepare the URL for the next request.
            url = sp.get_next_url()


    async def _asearch(
        self,
        query: str, 
        tld: Optional[str] = 'com', 
        lang: Optional[str] = 'en', 
        tbs: Optional[str] = '0', 
        safe: Optional[str] = 'off', 
        num: Optional[int] = 10, 
        start: Optional[int] = 0,
        stop: Optional[int] = None, 
        pause: Optional[float] = 2.0, 
        country: Optional[str] = '', 
        include_title: Optional[bool] = False,
        include_description: Optional[bool] = False,
        extra_params: Optional[Dict[str,str]] = None,
        user_agent: Optional[str] = None, 
        verify_ssl: Optional[bool] = True,
        **kwargs,
    ) -> AsyncGenerator[RT, None]:  # sourcery skip: low-code-quality
        """
        Searches the query
        """
        hashes = set()

        # Count the number of links yielded.
        count = 0

        # Prepare the search string.
        query = quote_plus(query)

        # If no extra_params is given, create an empty dictionary.
        # We should avoid using an empty dictionary as a default value
        # in a function parameter in Python.
        if not extra_params: extra_params = {}
        if extra_params: self.validate_extra_params(extra_params)

        sp = SearchParams(
            query = query,
            tld = tld,
            lang = lang,
            tbs = tbs,
            safe = safe,
            num = num,
            start = start,
            stop = stop,
            country = country,
            include_title = include_title,
            include_description = include_description,
        )

        # Grab the cookie from the home page.
        await self.aget_page(sp.url_home, user_agent, **kwargs)

        url = sp.start_url

        # Loop until we reach the maximum result, if any (otherwise, loop forever).
        while not sp.stop or count < sp.stop:

            # Remember last count to detect the end of results.
            last_count = count

            # Append extra GET parameters to the URL.
            # This is done on every iteration because we're
            # rebuilding the entire URL at the end of this loop.
            url = self.append_extra_params(url, extra_params)

            # Sleep between requests.
            # Keeps Google from banning you for making too many requests.
            await asyncio.sleep(get_random_jitter(pause))

            # Request the Google Search results page.
            html = await self.aget_page(url, user_agent, **kwargs)
            soup = BeautifulSoup(html, 'html.parser')

            # Parse the response and get every anchored URL.
            anchors = self.extract_anchors(soup)
            desc_anchors = self.extract_description(soup)
            # Process every anchored URL.
            for (a, desc) in zip(anchors, desc_anchors):
                
                result = sp.extract_result(a, desc, hashes)
                if not result: continue

                # Yield the result.
                yield result

                # Increase the results counter.
                # If we reached the limit, stop.
                count += 1
                if sp.stop and count >= sp.stop: return

            # End if there are no more results.
            # XXX TODO review this logic, not sure if this is still true!
            if last_count == count: break

            # Prepare the URL for the next request.
            url = sp.get_next_url()


    def search(
        self,
        query: str, 
        tld: Optional[str] = 'com', 
        lang: Optional[str] = 'en', 
        tbs: Optional[str] = '0', 
        safe: Optional[str] = 'off', 
        num: Optional[int] = 10, 
        start: Optional[int] = 0,
        stop: Optional[int] = None, 
        pause: Optional[float] = 2.0, 
        country: Optional[str] = '', 
        include_title: Optional[bool] = False,
        include_description: Optional[bool] = False,
        extra_params: Optional[Dict[str,str]] = None,
        user_agent: Optional[str] = None, 
        verify_ssl: Optional[bool] = True,
        **kwargs,
    ) -> Generator[RT, None, None]:  # sourcery skip: low-code-quality
        """
        Searches the query
        """
        yield from self._search(
            query = query, 
            tld = tld, 
            lang = lang, 
            tbs = tbs, 
            safe = safe, 
            num = num, 
            start = start,
            stop = stop, 
            pause = pause, 
            country = country, 
            include_title = include_title,
            include_description = include_description,
            extra_params = extra_params,
            user_agent = user_agent, 
            verify_ssl = verify_ssl,
            **kwargs,
        )

    async def asearch(
        self,
        query: str, 
        tld: Optional[str] = 'com', 
        lang: Optional[str] = 'en', 
        tbs: Optional[str] = '0', 
        safe: Optional[str] = 'off', 
        num: Optional[int] = 10, 
        start: Optional[int] = 0,
        stop: Optional[int] = None, 
        pause: Optional[float] = 2.0, 
        country: Optional[str] = '', 
        include_title: Optional[bool] = False,
        include_description: Optional[bool] = False,
        extra_params: Optional[Dict[str,str]] = None,
        user_agent: Optional[str] = None, 
        verify_ssl: Optional[bool] = True,
        **kwargs,
    ) -> AsyncGenerator[RT, None]:  # sourcery skip: low-code-quality
        """
        Searches the query
        """
        async for item in self._asearch(
            query = query, 
            tld = tld, 
            lang = lang, 
            tbs = tbs, 
            safe = safe, 
            num = num, 
            start = start,
            stop = stop, 
            pause = pause, 
            country = country, 
            include_title = include_title,
            include_description = include_description,
            extra_params = extra_params,
            user_agent = user_agent, 
            verify_ssl = verify_ssl,
            **kwargs,
        ):
            yield item

