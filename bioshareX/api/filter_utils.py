from django.db import models
from functools import partial

from django.db.models.expressions import RawSQL


# adapted from https://awstip.com/querying-djangos-jsonfield-a2914f5d4b91
def gen_sql_filter_json_array(model: models.Model, lookup_path: str, nested_key: str, query: str='ILIKE', lookup_value: str='') -> RawSQL:
    """
    Filter a queryset on a nested JSON key in an array field

    :param models.Model model: Your Django model to filter on
    :param str lookup_path: The lookup path of the array field/key in Postgres format e.g `data->"sub-key1"->"sub-key2"`
    :param str nested_key: The name of the nested key to filter on
    :param str lookup_value: The value to match/filter the queryset on
    """
    table_name = model._meta.db_table
    search_string = f"%{lookup_value}%"
    col_type = 'text'
    if query == 'ILIKE':
        clause = f"{nested_key} ILIKE %s "
        params = [search_string]
    elif query == 'not null':
        clause = f"{nested_key} is not null "
        params = []
    else:
        raise Exception(f"Unsupported query type {query}")
    query = (
        f"""SELECT "{table_name}".id FROM jsonb_to_recordset({lookup_path})
        AS temp_filter_table({nested_key} {col_type})
        WHERE {clause}"""
    )
    return RawSQL(sql=query, params=params)