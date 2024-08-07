
import jinja2
from typing import Dict

init_sql_schema_script = """
BEGIN;
CREATE TABLE IF NOT EXISTS {{ tablename }}(
    {%- for name, field in sql_fields.items() %}
    {{ name }} {{ field }}{% if not loop.last %},{% endif %}
    {%- endfor %}
);
CREATE VIRTUAL TABLE IF NOT EXISTS {{ tablename }}_fts
USING FTS5(
    {%- for name in sql_fields %}
    {{ name }},
    {%- endfor %}
    tokenize = "{{ tokenize or 'trigram' }}",
    content = "{{ tablename }}"
);
CREATE TRIGGER IF NOT EXISTS {{ tablename }}_ai AFTER INSERT ON {{ tablename }} BEGIN
    INSERT INTO {{ tablename }}_fts({% for name in sql_fields %}{{ name }}{% if not loop.last %}, {% endif %}{% endfor %})
    VALUES({% for name in sql_fields %}new.{{ name }}{% if not loop.last %}, {% endif %}{% endfor %});
END;
CREATE TRIGGER IF NOT EXISTS {{ tablename }}_ad AFTER DELETE ON {{ tablename }} BEGIN
    INSERT INTO {{ tablename }}_fts({{ tablename }}_fts, {% for name in sql_fields %}{{ name }}{% if not loop.last %}, {% endif %}{% endfor %})
    VALUES('delete', {% for name in sql_fields %}old.{{ name }}{% if not loop.last %}, {% endif %}{% endfor %});
END;
COMMIT;
"""


index_sql_query = """
INSERT INTO {{ tablename }}({{ sql_insert }}) VALUES ({{ sql_insert_q }})
ON CONFLICT({{ sql_pkey }}) DO UPDATE 
SET
    {%- for name, field in sql_fields.items() %}
    {%- if name != sql_pkey %}
    {{ name }} = excluded.{{ name }}{% if not loop.last %},{% endif %}
    {%- endif %}
    {%- endfor %}
"""

insert_sql_query = """
INSERT INTO {{ tablename }}({{ sql_insert }}) VALUES ({{ sql_insert_q }})
ON CONFLICT({{ sql_pkey }}) DO UPDATE
SET
    {%- for name in sql_insert_fields %}
    {%- if name != sql_pkey and name in sql_insert_fields %}
    {{ name }} = excluded.{{ name }}{% if not loop.last %},{% endif %}
    {%- endif %}
    {%- endfor %}
"""


search_sql_query = """
SELECT {% if return_fields %}{% for field in return_fields %}{{ field }}{% if not loop.last %}, {% endif %}{% endfor %}{% elif return_id_only %}{{ sql_pkey }}{% else %}*{% endif %}, rank
FROM {{ tablename }}_fts 
WHERE {{ query }}
ORDER BY rank
{%- if limit is defined and limit %}
LIMIT {{ limit }}
{%- endif %}
{%- if skip is defined and skip %}
OFFSET {{ skip }}
{%- endif %};
"""

# Refresh the underlying item
refresh_sql_query = """
SELECT * FROM {{ tablename }} WHERE {{ sql_pkey }} = ?
"""

count_total_sql_query = """
SELECT COUNT(*) FROM {{ tablename }} WHERE {{ sql_pkey }} is not null
"""

update_field_attribute_sql_query = """
UPDATE {{ tablename }} 
SET
    {{ name }} = ?
WHERE {{ sql_pkey }} = ?
"""
"""
SELECT rowid FROM {{ tablename }}_fts WHERE {{ sql_pkey }} = ?
    DELETE FROM {{ tablename }}_fts WHERE rowid = rowid
"""

# Delete doesn't currently work.
delete_row_sql_query = """
DELETE FROM {{ tablename }} WHERE {{ sql_pkey }} = ?
"""

SqliteTemplates: Dict[str, jinja2.Template] = {
    'init': jinja2.Template(init_sql_schema_script),
    'index': jinja2.Template(index_sql_query),
    'insert': jinja2.Template(insert_sql_query),
    'search': jinja2.Template(search_sql_query),
    'refresh': jinja2.Template(refresh_sql_query),
    'count_total': jinja2.Template(count_total_sql_query),
    'update_field_attribute': jinja2.Template(update_field_attribute_sql_query),
    'delete': jinja2.Template(delete_row_sql_query),
}