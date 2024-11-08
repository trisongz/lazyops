


GIT_PREFIXES = ('gh://', 'git://', 'hf://')
URI_PREFIXES = (
    'gs://', 
    's3://', 
    'az://', 
    'minio://', 'mio://', 'mc://', 
    's3c://', 
    'r2://', 
    'wsbi://'
) + GIT_PREFIXES

URI_SCHEMES = frozenset((
    'gs', 
    's3', 
    'az', 
    'minio', 'mio', 'mc',
    's3c', 
    'r2', 
    'wsbi', 
    'gh', 
    'git', 
    'hf'
))

URI_MAP_ROOT = {
    'gs://': '/gs/',
    's3://': '/s3/',
    'az://': '/azure/',

    'mio://': '/minio/',
    'minio://': '/minio/',
    'mc://': '/minio/',
    's3c://': '/s3c/',
    'r2://': '/r2/',
    'wsbi://': '/wasabi/',

    'gh://': '/github/',
    'git://': '/git/',
    'hf://': '/huggingface/',
}

PROVIDER_MAP = {
    'gs': 'GoogleCloudStorage',
    's3': 'AmazonS3',
    'az': 'Azure',
    'mio': 'MinIO',
    'minio': 'MinIO',
    'mc': 'MinIO',
    's3c': 'S3Compatible',
    'r2': 'CloudFlare',
    'wsbi': 'Wasabi',
    'gh': 'Github',
    'git': 'Git',
    'hf': 'HuggingFace',
}

