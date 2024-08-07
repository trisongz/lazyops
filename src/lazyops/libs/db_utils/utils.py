import datetime

def convert_date_to_rfc3339(date: str) -> str:
    """
    Converts a date to RFC3339 format, as Weaviate requires dates to be in RFC3339 format including the time and
    timezone.

    If the provided date string does not contain a time and/or timezone, we use 00:00 as default time
    and UTC as default time zone.
    """
    parsed_datetime = datetime.datetime.fromisoformat(date)
    return (
        f"{parsed_datetime.isoformat()}Z"
        if parsed_datetime.utcoffset() is None
        else parsed_datetime.isoformat()
    )
