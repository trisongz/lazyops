
from pprint import pprint
from lazyops.lazysources.gdelt import GDELT, GDELTFilters
from lazyops import timer

f = GDELTFilters(
    keyword = "climate change",
    start_date = "2021-05-10",
    end_date = "2021-05-15",
)

gd = GDELT(result_format='obj')

# Search for articles matching the filters

def print_article(filter_lang='English', total_num=5):
    start = timer()
    articles = gd.article_search(f)
    
    print('Total Articles in Query: ', len(articles))
    print('First Article URL: ', articles[0].url)
    print('First Article Data \n', articles)
    print('Done in: ', start.ablstime)

    filtered = [a for a in articles if a.language == filter_lang]
    total_num = min(total_num, len(filtered))
    for n, a in enumerate(filtered):
        if n >= total_num:
            break
        print(f'----- Parsing Article {n} -----')
        a.parse()
        pprint(a)
    print(f'Completed Parsing {total_num} Articles in: ', start.ablstime)

if __name__ == '__main__':
    print_article()