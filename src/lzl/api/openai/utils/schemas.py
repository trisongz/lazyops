from __future__ import annotations

"""
Schema Helpers for OpenAI
"""
import math
import functools
from lzl.types.base import get_pydantic_schema, PYDANTIC_VERSION
from typing import TYPE_CHECKING, Any, Sequence



if PYDANTIC_VERSION == 2:
    from pydantic.json_schema import GenerateJsonSchema as BaseGenerateJsonSchema

    if TYPE_CHECKING:
        from pydantic.config import JsonValue
        from pydantic_core import CoreSchema, PydanticOmit, core_schema
        from pydantic.json_schema import JsonSchemaValue, CoreSchemaField

    """
    Some type-specific keywords are not yet supported
    Notable keywords not supported include:

    For strings: minLength, maxLength, pattern, format
    For numbers: minimum, maximum, multipleOf
    For objects: patternProperties, unevaluatedProperties, propertyNames, minProperties, maxProperties
    For arrays: unevaluatedItems, contains, minContains, maxContains, minItems, maxItems, uniqueItems
    """

    hidden_fields = [
        'function_name',
        'function_model',
        'function_duration',
        'function_client_name',
    ]


    class GenerateJsonSchema(BaseGenerateJsonSchema):
        """
        Patched GenerateJsonSchema to support pydantic v2
        """

        def int_schema(self, schema: 'core_schema.IntSchema') -> 'JsonSchemaValue':
            """Generates a JSON schema that matches an int value.

            Args:
                schema: The core schema.

            Returns:
                The generated JSON schema.
            """
            # currently not supported:
            # minimum, maximum, multipleOf
            json_schema: dict[str, Any] = {'type': 'integer'}
            self.update_with_validations(json_schema, schema, self.ValidationsMapping.numeric)
            json_schema = {k: v for k, v in json_schema.items() if v not in {math.inf, -math.inf}}
            for key in {'minimum', 'maximum', 'multipleOf'}:
                if key in json_schema:
                    _ = json_schema.pop(key)
            return json_schema
        

        def list_schema(self, schema: 'core_schema.ListSchema') -> 'JsonSchemaValue':
            """Returns a schema that matches a list schema.

            Args:
                schema: The core schema.

            Returns:
                The generated JSON schema.
            """
            # currently not supported:
            # unevaluatedItems, contains, minContains, maxContains, minItems, maxItems, uniqueItems
            items_schema = {} if 'items_schema' not in schema else self.generate_inner(schema['items_schema'])
            json_schema = {'type': 'array', 'items': items_schema}
            self.update_with_validations(json_schema, schema, self.ValidationsMapping.array)
            for key in {'unevaluatedItems', 'contains', 'minContains', 'maxContains', 'minItems', 'maxItems', 'uniqueItems'}:
                if key in json_schema:
                    _ = json_schema.pop(key)
            return json_schema
        

        def str_schema(self, schema: 'core_schema.StringSchema') -> 'JsonSchemaValue':
            """Generates a JSON schema that matches a string value.

            Args:
                schema: The core schema.

            Returns:
                The generated JSON schema.
            """
            # currently not supported:
            # minLength, maxLength, pattern, format
            json_schema = {'type': 'string'}
            self.update_with_validations(json_schema, schema, self.ValidationsMapping.string)
            for key in {'minLength', 'maxLength', 'pattern', 'format'}:
                if key in json_schema:
                    _ = json_schema.pop(key)
            return json_schema


        def default_schema(self, schema: 'core_schema.WithDefaultSchema'):
            """Generates a JSON schema that matches a schema with a default value.

            Args:
                schema: The core schema.

            Returns:
                The generated JSON schema.
            """
            # We remove the default value from the schema since it isn't needed
            # during the generation but can be used during validation.
            return self.generate_inner(schema['schema'])

        def handle_ref_overrides(self, json_schema: JsonSchemaValue) -> JsonSchemaValue:
            """It is not valid for a schema with a top-level $ref to have sibling keys.

            During our own schema generation, we treat sibling keys as overrides to the referenced schema,
            but this is not how the official JSON schema spec works.

            Because of this, we first remove any sibling keys that are redundant with the referenced schema, then if
            any remain, we transform the schema from a top-level '$ref' to use allOf to move the $ref out of the top level.
            (See bottom of https://swagger.io/docs/specification/using-ref/ for a reference about this behavior)
            """
            json_schema = super().handle_ref_overrides(json_schema)
            if 'allOf' in json_schema:
                ref = json_schema.pop('allOf')
                json_schema.update(ref[0])
                # Remove description from here
                if 'description' in json_schema:
                    _ = json_schema.pop('description')
            return json_schema

        def field_is_required(
            self,
            field: 'core_schema.ModelField' | 'core_schema.DataclassField' | 'core_schema.TypedDictField',
            total: bool,
        ) -> bool:
            """Whether the field should be marked as required in the generated JSON schema.
            (Note that this is irrelevant if the field is not present in the JSON schema.).

            Args:
                field: The schema for the field itself.
                total: Only applies to `TypedDictField`s.
                    Indicates if the `TypedDict` this field belongs to is total, in which case any fields that don't
                    explicitly specify `required=False` are required.

            Returns:
                `True` if the field should be marked as required in the generated JSON schema, `False` otherwise.
            """
            # if self.mode == 'serialization' and self._config.json_schema_serialization_defaults_required:
            #     return not field.get('serialization_exclude')
            # if field.
            # print(field)
            # print(field['metadata']['pydantic_js_annotation_functions'])
            return True

        def _named_required_fields_schema(
            self, named_required_fields: Sequence[tuple[str, bool, 'CoreSchemaField']],
        ):
            """
            Generate a JSON Schema for the required fields.
            """
            json_schema = super()._named_required_fields_schema(named_required_fields)
            json_schema['additionalProperties'] = False
            return json_schema
        
    _excluded_fields = ['function_name', 'function_model', 'function_duration', 'function_client_name', 'function_usage']
    
    class FunctionGenerateJsonSchema(GenerateJsonSchema):

        def _named_required_fields_schema(
            self, named_required_fields: Sequence[tuple[str, bool, 'CoreSchemaField']]
        ) -> JsonSchemaValue:
            """
            Generate a JSON Schema for the required fields.
            """
            required_fields = [
                (name, required, field)
                for name, required, field in named_required_fields
                if name not in _excluded_fields
            ]
            return super()._named_required_fields_schema(required_fields)

    
    generate_json_schema = functools.partial(get_pydantic_schema, schema_generator = GenerateJsonSchema)
    function_generate_json_schema = functools.partial(get_pydantic_schema, schema_generator = FunctionGenerateJsonSchema)
else:
    generate_json_schema = get_pydantic_schema
    function_generate_json_schema = get_pydantic_schema
