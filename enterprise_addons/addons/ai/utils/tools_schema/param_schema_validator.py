class ParamSchemaValidator:

    AVAILABLE_TYPES = ['string', 'number', 'integer', 'boolean', 'array', 'object', 'null']
    REQUIRED_PARAMETER_ATTRIBUTES = ['type']
    REQUIRED_PARAMETER_ATTRIBUTES_BY_TYPE = {
        'array': ['items'],
        'string': ['maxLength'],
        'object': ['properties', 'required']
    }
    OPTIONAL_PARAMETER_ATTRIBUTES = ['pattern', 'description', 'enum', 'anyOf', 'minimum']

    def __init__(self, param_name, param_definition):
        self.param_name = param_name
        self.param_definition = param_definition
        self.param_type = self.param_definition.get('type')

    def _validate(self):
        # Handle anyOf case - validates multiple alternative schemas
        if 'anyOf' in self.param_definition:
            self._validate_anyof()
            return

        self._check_missing_required_attributes()
        self._check_unsupported_attributes()
        self._is_valid_param_type()
        self._check_pattern_only_with_allowed_types()
        self._check_minimum_only_with_allowed_types()
        if self.param_type == 'array':
            self._perform_array_checks()
        elif self.param_type == 'object':
            self._perform_object_checks()

    def _check_missing_required_attributes(self):
        missing_required_attributes = []
        for required_attribute in self.REQUIRED_PARAMETER_ATTRIBUTES:
            if required_attribute not in self.param_definition:
                missing_required_attributes.append(required_attribute)

        if missing_required_attributes:
            raise ValueError(
                f"The attributes '{missing_required_attributes}' must be defined for the parameter '{self.param_name}'."
            )

    def _check_unsupported_attributes(self):
        unsupported_attributes = [
            attribute for attribute in list(self.param_definition.keys())
            if attribute not in self._get_supported_param_attributes()
        ]
        if unsupported_attributes:
            raise ValueError(
                f"The attributes '{unsupported_attributes}' defined for the param '{self.param_name}' are not supported."
            )

    def _get_supported_param_attributes(self):
        return (
            self.REQUIRED_PARAMETER_ATTRIBUTES
            + self.REQUIRED_PARAMETER_ATTRIBUTES_BY_TYPE.get(self.param_type, [])
            + self.OPTIONAL_PARAMETER_ATTRIBUTES
        )

    def _check_pattern_only_with_allowed_types(self):
        pattern = self.param_definition.get('pattern')
        if pattern and self.param_type not in ['string', 'array']:
            raise ValueError(
                f"The pattern attribute cannot be defined for the parameter '{self.param_name}'. "
                "The pattern attribute can only be defined for string parameters or arrays whose items are only of the type string."
            )

    def _check_minimum_only_with_allowed_types(self):
        if 'minimum' not in self.param_definition:
            return
        minimum = self.param_definition['minimum']
        if self.param_type not in ('integer', 'number'):
            raise ValueError(
                f"The minimum attribute cannot be defined for the parameter '{self.param_name}'. "
                "The minimum attribute can only be defined for integer or number parameters."
            )
        if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
            raise TypeError(
                f"The minimum attribute for the parameter '{self.param_name}' must be a number."
            )

    def _is_valid_param_type(self):
        if self.param_type not in self.AVAILABLE_TYPES:
            raise ValueError(
                f"The type '{self.param_type}' of parameter '{self.param_name}' is wrong. The available types are '{self.AVAILABLE_TYPES}'."
            )

    def _perform_array_checks(self):
        self._check_missing_required_attributes_by_type('array')
        self._check_array_item_types()
        self._check_pattern_defined_only_if_string_array_item()

    def _check_missing_required_attributes_by_type(self, param_type):
        missing_required_attributes = []
        for required_attribute in self.REQUIRED_PARAMETER_ATTRIBUTES_BY_TYPE.get(param_type, []):
            if required_attribute not in self.param_definition:
                missing_required_attributes.append(required_attribute)

        if missing_required_attributes:
            raise ValueError(
                f"The attributes '{missing_required_attributes}' must be defined for a parameter of type '{self.param_type}'. "
                f"They are missing for the parameter '{self.param_name}'."
            )

    def _check_array_item_types(self):
        failure_message = (
            f"The types of the items of the 'array' param '{self.param_name}' are not defined correctly. "
            "The types of the items must be defined as ('items': {'type': 'string'}) if all items are of the same primitive type, "
            "('items': {'type': 'object', 'properties': {...}, 'required': [...]}) for objects, "
            "or ('items': { 'anyOf': [ {'type': 'string'}, {'type': 'number'} ] }) if items are of different types"
        )
        array_item_schema = self.param_definition.get('items')
        if (
            not isinstance(array_item_schema, dict)
            or array_item_schema.get('anyOf') and not isinstance(array_item_schema['anyOf'], list)
            or ('anyOf' in array_item_schema and 'type' in array_item_schema)
        ):
            raise ValueError(
                failure_message
            )
        allowed_array_types = set(self.AVAILABLE_TYPES) - {'array'}
        array_item_schemas = array_item_schema.get('anyOf') if 'anyOf' in array_item_schema else [array_item_schema]
        for item_schema in array_item_schemas:
            if not isinstance(item_schema, dict) or not item_schema.get('type'):
                raise ValueError(
                    failure_message
                )
            item_type = item_schema['type']
            if item_type not in allowed_array_types:
                raise ValueError(
                    f"The type '{item_type}' of the items of the 'array' parameter '{self.param_name}' is wrong. The available types are '{allowed_array_types}'.",
                )
            if item_type == 'object':
                validate_schema(item_schema)

    def _check_pattern_defined_only_if_string_array_item(self):
        pattern = self.param_definition.get('pattern')
        array_item_types = self.param_definition.get('items')
        array_item_types = array_item_types.get('anyOf', [array_item_types])
        if pattern and not (len(array_item_types) == 1 and array_item_types[0]['type'] == 'string'):
            raise ValueError(
                f"The pattern attribute cannot be defined for the parameter '{self.param_name}'. "
                "The pattern attribute can only be defined for string parameters or arrays whose items are only of the type string."
            )

    def _perform_object_checks(self):
        self._check_missing_required_attributes_by_type('object')
        self._check_required_attribute_is_list()
        self._validate_object_properties()

    def _check_required_attribute_is_list(self):
        if not isinstance(self.param_definition['required'], list):
            raise TypeError(
                f"The attribute 'required' for the object param '{self.param_name}' must be a 'list' containing "
                "the required properties of the object or empty if all of them are not required."
            )

    def _validate_object_properties(self):
        object_properties = self.param_definition['properties']
        for object_property_name, object_property_definition in object_properties.items():
            param_validator = ParamSchemaValidator(object_property_name, object_property_definition)
            param_validator._validate()

    def _validate_anyof(self):
        """Validate anyOf property-level schemas.

        anyOf allows a property to match one or more of the provided schemas.
        Each schema in the anyOf array must be valid according to the validator rules.
        """
        anyof_schemas = self.param_definition.get('anyOf')

        if not isinstance(anyof_schemas, list) or not anyof_schemas:
            raise ValueError(
                f"The 'anyOf' attribute for parameter '{self.param_name}' must be a non-empty list of schemas."
            )

        # Validate each alternative schema
        for idx, schema in enumerate(anyof_schemas):
            if not isinstance(schema, dict):
                raise TypeError(
                    f"Each schema in 'anyOf' for parameter '{self.param_name}' must be an object. "
                    f"Schema at index {idx} is not an object."
                )

            # Recursively validate each schema
            schema_validator = ParamSchemaValidator(f"{self.param_name}[anyOf[{idx}]]", schema)
            schema_validator._validate()


def validate_input(input_schema, required_parameters):
    if (
        required_parameters is None
        or not isinstance(required_parameters, list)
    ):
        error_msg = (
            "The required properties should be specified as a list. i.e. 'required': [<property1_name>, <property2_name>, ...]."
            "If no properties are required, set required to an empty list 'required': []"
        )
        raise ValueError(error_msg)

    if missing_required_props := [prop for prop in required_parameters if prop not in input_schema]:
        error_msg = "Following properties are required but their definition is missing in the schema: " + ", ".join(missing_required_props)
        raise ValueError(error_msg)


def validate_schema(schema):
    parameters = schema.get("properties")
    required_parameters = schema.get("required")
    validate_input(parameters, required_parameters)
    for param_name, param_definition in parameters.items():
        param_validator = ParamSchemaValidator(param_name, param_definition)
        param_validator._validate()
