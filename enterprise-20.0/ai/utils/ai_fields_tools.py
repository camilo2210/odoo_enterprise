# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import requests
from datetime import datetime, UTC
from dateutil.parser import isoparse
from lxml import html
from markupsafe import Markup

try:
    from markdown2 import markdown
except ImportError:
    markdown = None

from odoo import fields
from odoo.exceptions import UserError
from odoo.tools import html_sanitize
from odoo.tools.mail import html_to_inner_content

from odoo.addons.ai.utils.ai_utils import get_text_from_parts

AI_FIELDS_INSTRUCTIONS = (
"""You are a system responsible for generating a value on an Odoo record.
You are not a conversational agent.
The user message contains instructions and might contain some information about the record (as an ORM snapshot) and the allowed values.
When an ORM snapshot is provided in the user message, all data values for the record will be enclosed in double curly braces.
If you cannot reliably generate a value (e.g. the appropriate value for selection/relational fields is unclear or unavailable even after attempting a web search), answer with `could_not_resolve` set to true and with an `unresolved_cause`.
When the ORM snapshot does not contain enough information to fulfill the request, use a web search to find the missing information. Only set `could_not_resolve` to true if the information cannot be found through web search either.
Rely on internal knowledge only for unchanging historical facts. In all other cases, do a web search to retrieve additional information.
Unless explicitly requested in the user message, answer in the same language used in the user message (in the request part)."""
)


class UnresolvedQuery(UserError):
    pass


def get_ai_value(record, field_descripiton, user_prompt, context_fields, allowed_values):
    """Query a LLM with the given prompt and return the cast value.

    :param record: the record for which the value should be obtained
    :param field: the field/property description for which the response should be cast
    :param user_prompt: the "user prompt" to pass to the LLM (the request)
    :param context_fields: list of field paths that needs to be included in the context dict
    :param allowed_values: a dict containing the values that are allowed

    :return: the value with the type expected for the given field type, or False if the value
        could not be cast or is not in allowed_values
    """
    field_type = field_descripiton['type']
    if field_type in ('many2many', 'many2one', 'selection', 'tags') and not allowed_values:
        raise UnresolvedQuery(record.env._("No allowed values are provided in the prompt."))
    record_context, file_parts = record._get_ai_context(context_fields)
    context = f"# Context\n## Current date\n{datetime.now(UTC).astimezone().replace(second=0, microsecond=0).isoformat()}"
    context += f'\n## Field info\n{json.dumps(field_descripiton)}'
    context += f'\n## Current record\n{{"model": "{record._name}", "id": {record.id}}}'
    if record_context != '{}':
        context += f"\n## ORM Snapshot\n{record_context}"
    if allowed_values:
        context += f"\n## Allowed Values\n{json.dumps(allowed_values)}"
    msg_parts = [{'type': 'text', 'text': f"# Action request\n{user_prompt}\n{context}"}]
    msg_parts.extend(file_parts)
    if field_type == 'boolean':
        field_schema = {
            'type': 'boolean',
            'description': 'The boolean to assign to the field'
        }
    elif field_type == 'char':
        field_schema = {
            'type': 'string',
            'description': 'The string to assign to the field. Must be short, concise, without any Markdown formatting, and without any technical data (such as record IDs, field labels, ...)'
        }
    elif field_type == 'date':
        field_schema = {
            'type': ['string', 'null'],
            'format': 'date',
            'description': 'The date to assign to the field. The year, month and day should be correct. Use null to leave the field empty',
        }
    elif field_type == 'datetime':
        field_schema = {
            'type': ['string', 'null'],
            'format': 'date-time',
            'description': 'The datetime to assign to the field. The year, month and day should be correct. The timezine must be included. Use null to leave the field empty'
        }
    elif field_type == 'integer':
        field_schema = {
            'type': 'integer',
            'description': "The whole number to assign to the field. If a number is expressed in words (e.g. '6.67 billion'), it must be converted into its full numeric form (e.g. '6670000000')"
        }
    elif field_type in ('float', 'monetary'):
        field_schema = {
            'type': 'number',
            'description': "The float to assign to the field"
        }
    elif field_type == 'html':
        field_schema = {
            'type': 'string',
            'description': 'The string to assign to the field. Must be well-structured Markdown, that may contain tables (the markdown will be converted to HTML after generation)'
        }
    elif field_type == 'text':
        field_schema = {
            'type': 'string',
            'description': 'The string to assign to the field. Must be a few sentences, without any Markdown formatting, and without any technical data (such as record IDs, field labels, ...)'
        }
    elif field_type == 'many2many':
        field_schema = {
            'type': 'array',
            'items': {
                'type': 'integer',
                'enum': list(allowed_values)
            },
            'description': 'The list of IDs of the records to assign to the field. Leave empty to leave the field empty'
        }
    elif field_type == 'many2one':
        field_schema = {
            'type': ['integer', 'null'],
            'enum': list(allowed_values) + [None],
            'description': 'The ID of the record to assign to the field. Use null to leave the field empty (eg. if no value matches the user query)'
        }
    elif field_type == 'selection':
        field_schema = {
            'type': ['string', 'null'],
            'enum': list(allowed_values) + [None],
            'description': 'The key of the selection value to assign to the field. Use null to leave the field empty'
        }
    elif field_type == 'tags':
        field_schema = {
            'type': 'array',
            'items': {
                'type': 'string',
                'enum': list(allowed_values)
            },
            'description': 'The list of keys of the tags to assign to the field. Leave empty to leave the field empty'
        }
    else:
        field_schema = {'type': 'text', 'description': 'The value to assign to the field'}

    schema = {
        'type': 'object',
        'properties': {
            'value': field_schema,
            'could_not_resolve': {
                'type': 'boolean',
                'description': 'True if the model cannot confidently resolve a value, typically due to missing information, inherent ambiguity, or unverifiable entities in the input.'
            },
            'unresolved_cause': {
                'type': ['string', 'null'],
                'description': 'Short explanation of what is missing or why no value could be confidently resolved. Required if could_not_resolve is true.'
            },
        },
        'required': ['value', 'could_not_resolve', 'unresolved_cause'],
        'additionalProperties': False
    }

    try:
        response = record.env['ai.session']._get_direct_response(
            instructions=AI_FIELDS_INSTRUCTIONS,
            message=msg_parts,
            schema=schema,
            web_grounding=True,
            usage="ai_field",
        )
    except requests.exceptions.Timeout:
        raise UserError(record.env._("Oops, the request timed out."))
    except requests.exceptions.ConnectionError:
        raise UserError(record.env._("Oops, the connection failed."))

    if not response:
        raise UserError(record.env._("Oops, an unexpected error occurred."))
    try:
        response = json.loads(get_text_from_parts(response), strict=False)
    except json.JSONDecodeError:
        raise UserError(record.env._("Oops, the response could not be processed."))
    if response.get('could_not_resolve'):
        raise UnresolvedQuery(response.get('unresolved_cause'))

    return parse_ai_response(
        response.get('value'),
        field_type,
        allowed_values,
    )


def get_field_prompt_vals(env, field, field_prompt=None):
    """Get the parsed prompt, the field paths inserted in the prompt and the allowed values for the
    given field. If field_prompt is given, the values are obtained from this prompt instead of the
    one defined on the field.

    :param field: the field from which to get the values
    :param field_prompt: prompt to use instead of the one defined on the field

    :return: (user_prompt, fields, allowed_values)
    """
    ai_params = env["ir.model.fields"]._get_field_ai_parameters(field)
    user_prompt, fields, allowed_values = parse_ai_prompt_values(env, field_prompt or ai_params.get("prompt"), field.comodel_name if field.relational else None)
    if field.type == 'selection':
        allowed_values = field._selection
    return user_prompt, fields, allowed_values  # do we need html_to_inner_content?


def get_property_prompt_vals(env, property_definition):
    """Get the parsed prompt, the field paths inserted in the prompt and the allowed values for the
    given property_definition.

    :param property_definition: the property definition from which to get the values

    :return: (user_prompt, fields, allowed_values)
    """
    property_type = property_definition.get('type')
    user_prompt = property_definition.get('system_prompt')
    user_prompt, fields, allowed_values = parse_ai_prompt_values(env, user_prompt, property_definition.get('comodel'))
    if property_type == 'selection':
        allowed_values = dict(property_definition.get('selection', {}))
    elif property_type == 'tags':
        allowed_values = {name: label for name, label, color in (property_definition.get('tags') or [])}
    return user_prompt, fields, allowed_values  # do we need html_to_inner_content?


def parse_ai_prompt_values(env, prompt, comodel, replace_prompt=True):
    """Parse the given prompt to extract the inserted field paths and record references.
    Replace fields paths by {{path}} placeholders and records by their display names if
    replace_prompt is True.

    Considering the following prompt:
    <p>
        Based on the document <span data-ai-field="attachment_id">Content</span> and
        <span data-ai-field="name">Name</span>, place it inside
        <span data-ai-record-id="17">Finance</span> or <span data-ai-record-id="19">Billing</span>
    </p>
    Where
    - "attachment_id" and "name" are inserted in the prompt by the end user with the /field command
    and are extracted and returned by this method so that they can be validated (ensure read access
    when the end user edits the prompt) or interpreted and added as context to the LLM to resolve
    the user query.

    - "Finance" and "Billing" records are inserted in the prompt by the end user with the /record
    command and are extracted and returned by this method so that they can be validated (ensure
    read access when the end user edits the prompt) or added as allowed values when resolving the
    user query (for relational fields)

    The method will return (prompt, field_paths, formatted_allowed_records|inserted_record_ids) as
    follows:
    - prompt: either the original prompt, either a cleaned prompt (field path replaced by brackets,
        html to text, records replaced by their display names) based on replace_prompt
    - field_paths: list of field paths from the prompt (from example: ['attachment_id', 'name'])
    - formatted_allowed_records: dict of allowed existing records from the prompt formatted with
        :meth:`_ai_format_records` if replace_prompt is True
    - inserted_record_ids: set of record ids inserted in the prompt, if replace_prompt is False
        (used for validation, should not filter non-existing records to raise missing errors)
    """
    tree = html.fromstring(prompt)

    prompt_fields = set()
    for prompt_field_element in tree.xpath('//span[@data-ai-field]'):
        field_path = prompt_field_element.attrib.get('data-ai-field')
        if replace_prompt:
            if field_path:
                prompt_field_element.text = f"{{{{{field_path}}}}}"
            else:
                prompt_field_element.drop_tree()
        prompt_fields.add(field_path)

    inserted_record_ids = set()
    formatted_allowed_records = {}
    if comodel:
        inserted_record_elements = tree.xpath('//span[@data-ai-record-id]')
        inserted_record_ids = {
            int(record_id)
            for inserted_record_element
            in inserted_record_elements
            if (record_id := inserted_record_element.attrib.get('data-ai-record-id'))
        }
        if replace_prompt:
            allowed_records_by_id = env[comodel].browse(inserted_record_ids).exists().grouped("id")
            for inserted_record_element in inserted_record_elements:
                if allowed_record := allowed_records_by_id.get(int(inserted_record_element.attrib.get('data-ai-record-id'))):
                    record_name_field = (
                        allowed_record._ai_rec_name
                        if hasattr(allowed_record, '_ai_rec_name')
                        else 'display_name'
                    )
                    inserted_record_element.text = allowed_record._ai_truncate(
                        allowed_record[record_name_field])
                else:
                    inserted_record_element.drop_tree()
            formatted_allowed_records = env[comodel].browse(allowed_records_by_id.keys())._ai_format_records()

    if replace_prompt:
        return html_to_inner_content(html.tostring(tree, encoding='unicode')), prompt_fields, formatted_allowed_records
    return prompt, prompt_fields, inserted_record_ids


def parse_ai_response(response, field_type, allowed_values):
    """Parse and cast a LLM response into the type expected for the given field type and checks
    that the value is in the set of allowed_values if given.

    :param response: a LLM response
    :param str field_type: the type of the field for which the response should be cast
    :param set allowed_values: a set of values that are allowed

    :return: the value with the type expected for the given field type, or False if the value
        could not be cast or is not in allowed_values
    """
    if not allowed_values:
        allowed_values = {}

    if field_type == 'datetime':
        if not response:
            return False
        try:
            return fields.Datetime.to_string(isoparse(response).astimezone(UTC))
        except ValueError:
            return False
        return response
    elif field_type == 'date':
        if not response:
            return False
        try:
            return fields.Datetime.to_string(isoparse(response))
        except ValueError:
            return False
        return response
    elif field_type in ('selection', 'many2one'):
        return response if response in allowed_values else False
    elif field_type in ('tags', 'many2many'):
        return [value for value in response if value in allowed_values]
    elif field_type == 'html':
        if markdown:
            raw_html = markdown(response, extras=['fenced-code-blocks', 'tables', 'strike', 'cuddled-lists']).rstrip('\n')
            return html_sanitize(raw_html or "")
        return html_sanitize(response or "")
    else:
        return response


def ai_field_insert(field_path, field_label):
    return Markup('<span data-ai-field="%s">%s</span>') % (field_path, field_label)
