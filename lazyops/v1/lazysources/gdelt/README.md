# LazySources - GDelt

Lazy Data Source for [GDELT](https://www.gdeltproject.org/)

Extended from [gdelt-doc-api](https://github.com/alex9smith/gdelt-doc-api).
Credit to original authors @alex9smith and @FelixKleineBoesing

- Async Support
- Multiple Result Formats Available
    - Dict
    - Pandas Dataframe
    - JSON string
    - Object: GDELTArticle class
        - Can be called on to fully parse the URL
        - `article = articles[0]; article.parse()`


API client for the GDELT 2.0 Doc API. Supports Async Methods

```python
from lazyops.lazysources.gdelt import GDELT, GDELTFilters

# Formats = [
# 'obj', # GDELTArticle which can be called to extract the url
# 'json', Pure JSON String Output
# 'dict', Pyhon Dict
# 'pd', Pandas DF
# ]

f = GDELTFilters(
    keyword = "climate change",
    start_date = "2021-05-10",
    end_date = "2021-05-15"
)
gd = GDELT(result_format='obj')

# Search for articles matching the filters
articles = gd.article_search(f)

# Or call method .search directly
articles = gd.search(method='article', filters=f)

# Async Methods
articles = await gd.async_search(method='article', filters=f)
articles = await gd.async_article_search(f)

# Parsing Articles - Syncronous
english_articles = [i for i in articles if i.language == 'English']

for article in english_articles:
    article.parse()
    print(article.text)

# Parsing Articles - Asyncronous
english_articles = [await article.async_parse() for article in english_articles]


# Get a timeline of the number of articles matching the filters
# timeline = gd.timeline_search("timelinevol", f)


```

### Article List
The article list mode of the API generates a list of news articles that match the filters.
The client returns this as a pandas DataFrame with columns `url`, `url_mobile`, `title`,
`seendate`, `socialimage`, `domain`, `language`, `sourcecountry`.

### Timeline Search
There are 5 available modes when making a timeline search:
* `timelinevol` - a timeline of the volume of news coverage matching the filters,
    represented as a percentage of the total news articles monitored by GDELT.
* `timelinevolraw` - similar to `timelinevol`, but has the actual number of articles
    and a total rather than a percentage
* `timelinelang` - similar to `timelinevol` but breaks the total articles down by published language.
    Each language is returned as a separate column in the DataFrame.
* `timelinesourcecountry` - similar to `timelinevol` but breaks the total articles down by the country
    they were published in. Each country is returned as a separate column in the DataFrame.
* `timelinetone` - a timeline of the average tone of the news coverage matching the filters.
    See [GDELT's documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
    for more information about the tone metric.

### Construct filters for the GDELT API.
Filters for `keyword`, `domain`, `domain_exact`, `country` and `theme`
can be passed either as a single string or as a list of strings. If a list is
passed, the values in the list are wrapped in a boolean OR.
Params
------
* `start_date`
    The start date for the filter in YYYY-MM-DD format. The API officially only supports the
    most recent 3 months of articles. Making a request for an earlier date range may still
    return data, but it's not guaranteed.
    Must provide either `start_date` and `end_date` or `timespan`
* `end_date`
    The end date for the filter in YYYY-MM-DD format.
* `timespan`
    A timespan to search for, relative to the time of the request. Must match one of the API's timespan
    formats - https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
    Must provide either `start_date` and `end_date` or `timespan`
* `num_records`
    The number of records to return. Only used in article list mode and can be up to 250.
* `keyword`
    Return articles containing the exact phrase `keyword` within the article text.
* `domain`
    Return articles from the specified domain. Does not require an exact match so
    passing "cnn.com" will match articles from "cnn.com", "subdomain.cnn.com" and "notactuallycnn.com".
* `domain_exact`
    Similar to `domain`, but requires an exact match.
* `near`
    Return articles containing words close to each other in the text. Use `near()` to construct.
    eg. near = near(5, "airline", "climate").
* `repeat`
    Return articles containing a single word repeated at least a number of times. Use `repeat()`
    to construct. eg. repeat = repeat(3, "environment").
    If you want to construct a filter with multiple repeated words, construct with `multi_repeat()`
    instead. eg. repeat = multi_repeat([(2, "airline"), (3, "airport")], "AND")
* `country`
    Return articles published in a country, formatted as the FIPS 2 letter country code.
* `theme`
    Return articles that cover one of GDELT's GKG Themes. A full list of themes can be
    found here: http://data.gdeltproject.org/api/v2/guides/LOOKUP-GKGTHEMES.TXT