from ._base import *

from .filters import GDELTFilters
from .models import GDELTArticle

class GDELTFormat(Enum):
    dict = 'dict'
    obj = 'obj'
    json = 'json'
    pandas = 'pd'


class GDELTMethods(Enum):
    article = 'article'
    timeline = 'timeline'

class GDELT:
    api_url = 'https://api.gdeltproject.org/api/v2/doc/doc'
    available_modes = ["artlist", "timelinevol", "timelinevolraw", "timelinetone", "timelinelang", "timelinesourcecountry"]

    def __init__(self, result_format: GDELTFormat = GDELTFormat.obj, json_parsing_max_depth: int = 100, *args, **kwargs) -> None:
        if isinstance(result_format, str): result_format = GDELTFormat[result_format]
        self.max_depth_json_parsing = json_parsing_max_depth
        self._output_format = result_format
        self.sess = LazySession()

    def return_article_result(self, articles: Dict = None):
        if not articles or not articles.get('articles'):
            return None
        if self._output_format.value == 'dict':
            return articles['articles']
        
        if self._output_format.value == 'pd':
            return pd.DataFrame(articles["articles"])
        
        if self._output_format.value == 'json':
            return LazyJson.dumps(articles['articles'])
        
        if self._output_format.value == 'obj':
            return [GDELTArticle(**article) for article in articles['articles']]
    
    def return_timeline_search(self, results: Dict = None):
        if not results:
            return None
        
        if self._output_format.value == 'dict':
            return results
        
        if self._output_format.value == 'pd':
            formatted = pd.DataFrame(results)
            formatted["datetime"] = pd.to_datetime(formatted["datetime"])
            return formatted
        
        if self._output_format.value == 'json':
            return LazyJson.dumps(results)
        
        if self._output_format.value == 'obj':
            return [LazyObject(res) for res in results]


    def article_search(self, filters: GDELTFilters) -> Union[pd.DataFrame, Dict, str]:
        articles = self._query("artlist", filters.query_string)
        return self.return_article_result(articles)

    def timeline_search(self, mode: str, filters: GDELTFilters) -> Union[pd.DataFrame, Dict, str]:
        timeline = self._query(mode, filters.query_string)
        results = {"datetime": [entry["date"] for entry in timeline["timeline"][0]["data"]]}
        for series in timeline["timeline"]:
            results[series["series"]] = [entry["value"] for entry in series["data"]]

        if mode == "timelinevolraw": results["All Articles"] = [entry["norm"] for entry in timeline["timeline"][0]["data"]]
        return self.return_timeline_search(results)
    
    def search(self, method: GDELTMethods, filters: GDELTFilters) -> Union[pd.DataFrame, Dict, str]:
        if method.value == 'article':
            return self.article_search(filters)
        if method.value == 'timeline':
            return self.timeline_search(filters)

    async def async_search(self, method: GDELTMethods, filters: GDELTFilters) -> Union[pd.DataFrame, Dict, str]:
        if method.value == 'article':
            return await self.async_article_search(filters)
        if method.value == 'timeline':
            return await self.async_timeline_search(filters)

    async def async_article_search(self, filters: GDELTFilters) -> Union[pd.DataFrame, Dict, str]:
        articles = await self._async_query("artlist", filters.query_string)
        return self.return_article_result(articles)

    async def async_timeline_search(self, mode: str, filters: GDELTFilters) -> Union[pd.DataFrame, Dict, str]:
        timeline = await self._async_query(mode, filters.query_string)
        results = {"datetime": [entry["date"] for entry in timeline["timeline"][0]["data"]]}
        for series in timeline["timeline"]:
            results[series["series"]] = [entry["value"] for entry in series["data"]]

        if mode == "timelinevolraw": results["All Articles"] = [entry["norm"] for entry in timeline["timeline"][0]["data"]]
        return self.return_timeline_search(results)
    
    def _decode_json(cls, content, max_recursion_depth: int = 100, recursion_depth: int = 0):
        try:
            result = LazyJson.loads(content, recursive=True)
        except Exception as e:
            if recursion_depth >= max_recursion_depth:
                raise ValueError("Max Recursion depth is reached. JSON can´t be parsed!")
            idx_to_replace = int(e.pos)
            if isinstance(content, bytes): content.decode("utf-8")
            json_message = list(content)
            json_message[idx_to_replace] = ' '
            new_message = ''.join(str(m) for m in json_message)
            return GDELT._decode_json(content=new_message, max_recursion_depth=max_recursion_depth, recursion_depth=recursion_depth+1)
        return result
    
    async def _async_decode_json(cls, content, max_recursion_depth: int = 100, recursion_depth: int = 0):
        try:
            result = LazyJson.loads(content, recursive=True)
        except Exception as e:
            if recursion_depth >= max_recursion_depth:
                raise ValueError("Max Recursion depth is reached. JSON can´t be parsed!")
            idx_to_replace = int(e.pos)
            if isinstance(content, bytes): content.decode("utf-8")
            json_message = list(content)
            json_message[idx_to_replace] = ' '
            new_message = ''.join(str(m) for m in json_message)
            return await GDELT._async_decode_json(content=new_message, max_recursion_depth=max_recursion_depth, recursion_depth=recursion_depth+1)
        return result

    def _query(self, mode: str, query_string: str) -> Dict:
        if mode not in GDELT.available_modes:
            raise ValueError(f"Mode {mode} not in supported API modes")
        resp = self.sess.fetch(url=GDELT.api_url, decode_json=False, method='GET', params={'query': query_string, 'mode': mode, 'format': 'json'})
        if resp.status_code not in [200, 202]:
            raise ValueError("The gdelt api returned a non-successful status code. This is the response message: {}".format(resp.text))
        return self._decode_json(resp.content, max_recursion_depth=self.max_depth_json_parsing)
    
    async def _async_query(self, mode: str, query_string: str) -> Dict:
        if mode not in GDELT.available_modes:
            raise ValueError(f"Mode {mode} not in supported API modes")
        resp = await self.sess.async_fetch(url=GDELT.api_url, decode_json=False, method='GET', params={'query': query_string, 'mode': mode, 'format': 'json'})
        if resp.status_code not in [200, 202]:
            raise ValueError("The gdelt api returned a non-successful status code. This is the response message: {}".format(resp.text))
        return await self._async_decode_json(resp.content, max_recursion_depth=self.max_depth_json_parsing)

