# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import json
from zoneinfo import ZoneInfo
from lxml import html
from lxml.etree import ParserError, XMLSyntaxError
from markupsafe import Markup

from odoo import api, models
from odoo.api import NewId
from odoo.exceptions import AccessError
from odoo.tools import OrderedSet
from odoo.tools.mail import html_to_inner_content
from odoo.tools.misc import formatLang

from odoo.addons.ai.utils.ai_image_tools import AI_SUPPORTED_IMG_TYPES


class Model(models.AbstractModel):
    _inherit = 'base'

    def _ai_truncate(self, value, size=60):
        # Limit the size of the field we can, to try to limit prompt injection...
        if not isinstance(value, str) or len(value) < size:
            return value
        return value[:max(0, size - 3)] + "..."

    def _ai_field_names_to_truncate(self):
        return ('name', 'display_name')

    def _ai_serialize_fields_data(self):
        if self._name != 'ir.attachment':
            try:
                self.env['ai.tool']._check_agent_model_access(self._name)
            except ValueError:
                return f"Data of {self._name} records cannot be used by AI Agents"
        fields_info = self.fields_get()
        result = {}

        for field_name, field_attrs in fields_info.items():
            try:
                field_type = field_attrs["type"]
                field_value = self[field_name]

                if field_type == 'char' and field_name in self._ai_field_names_to_truncate():
                    field_value = self._ai_truncate(field_value)
                # Handle relational fields
                elif field_type == "many2one":
                    result[field_name] = (
                        {'id': field_value.id, field_value._rec_name: self._ai_truncate(field_value.display_name)} if field_value else None
                    )
                elif field_type in ["one2many", "many2many"]:
                    linked_records = self.env[field_value._name].browse(field_value.ids)
                    if (
                        len(linked_records) > 50
                    ):  # there have been cases were too many linked records have flooded the context - avoid that by filtering them out
                        continue
                    else:
                        result[field_name] = [
                            {'id': record.id, field_value._rec_name: self._ai_truncate(record.display_name)} for record in linked_records
                        ]
                elif field_type == "binary":
                    continue  # we don't include binary fields in the record info JSON
                else:
                    # Handle basic field types (dates, etc.)
                    if isinstance(field_value, datetime.datetime):
                        user_tz = ZoneInfo(self.env.user.tz or 'UTC')
                        result[field_name] = (
                            field_value.astimezone(user_tz).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            if field_value
                            else None
                        )
                    elif isinstance(field_value, models.BaseModel):
                        # Handle unexpected recordset returns (shouldn't happen for non-relational fields)
                        result[field_name] = field_value.ids
                    else:
                        result[field_name] = field_value
            except AccessError:  # if the user doesn't have access to a field, don't include it in the AI's context
                continue

        return json.dumps(result, default=str)

    ################
    #  Extensions  #
    ################
    def _ai_read(self, fnames=None, files_parts=None, files_checksums=None):
        """Retrieve and format field values for LLM processing.
        If no field names are given, return the display name.
        This method can be overridden on any model that requires sending more than just the display
        name when its records are included in a prompt (such as attachments).
        Files are handled separately, as they must be sent independently to LLMs.

        :param fnames: list of field names to read and format
        :param files_parts: AIMessageParts
        :param files_checksums: set of the checksums of files whose data has already been retrieved

        :return: (vals_list, files_parts, files_checksums) where vals_list is a list of dicts mapping field names to
            their formatted values with one dictionary per record.
            files_parts is AIMessageParts of the files (it also includes the files_parts from the input :param: 'files_parts')
            files_checksums is a set of the checksums of files whose data
            has already been retrieved (it also includes the checksums from the input :param: 'files_checksums')
        """
        if not fnames:
            fnames = ['display_name']  # by default, send display names

        if not files_parts:
            files_parts = []
        if files_checksums is None:
            files_checksums = set()

        vals_list = self.read(fnames, load=None)

        for fname in fnames:
            field = self._fields.get(fname)
            if field.type in ('binary', 'image'):
                if field.attachment:
                    attachments = self.env['ir.attachment']._get_field_attachments(self, [fname])
                    __, files_parts, files_checksums = attachments._ai_read(None, files_parts, files_checksums)
                for record, vals in zip(self, vals_list):
                    raw = record[fname]
                    if not raw:
                        continue
                    checksum = self.env['ir.attachment']._compute_checksum(raw)
                    if checksum not in files_checksums:
                        mimetype = raw.mimetype
                        extension = mimetype.split("/")[-1]
                        if (is_supported_mimetype := extension in (*AI_SUPPORTED_IMG_TYPES, 'pdf')):
                            # todo: keep 5 pages max and resize images
                            content = vals[fname]
                            if content:
                                content = content['content']
                        else:
                            try:
                                content = self.env['ir.attachment']._index(raw, mimetype, checksum=checksum)
                            except TypeError:
                                content = self.env['ir.attachment']._index(raw, mimetype)
                        if is_supported_mimetype:
                            files_checksums.add(checksum)
                            files_parts.append({
                                'type': 'inline_data',
                                'mimetype': mimetype,
                                'data': content or '',
                                'metadata': {
                                    'image_path': f'/web/image/{self._name}/{vals["id"]}/{fname}'
                                }
                            })
                        else:
                            files_checksums.add(checksum)
                            files_parts.append({
                                'type': 'text',
                                'text': content or '',
                            })
                    vals[fname] = f"<file_{checksum}/>"
            elif field.type in ('date', 'datetime'):
                for vals in vals_list:
                    vals[fname] = field.to_string(vals[fname])
            elif field.type == 'html' and not self.env.context.get('ai_read_preserve_html'):
                for vals in vals_list:
                    vals[fname] = html_to_inner_content(vals[fname])
            elif field.type in ('many2many', 'many2one', 'many2one_reference', 'one2many', 'reference'):
                # can't use result of read because we might have temporary records (with NewId), so
                # the ids won't be the ids we expect (origin ids or none for virtual records)
                vals_by_ids = {vals['id']: vals for vals in vals_list}
                for record in self:
                    record_vals = vals_by_ids[record.id]
                    co_records = record[fname]
                    if not co_records:
                        record_vals[fname] = False  # keep falsy values consistent for the LLM
                    if field.type == 'many2one_reference':
                        record_vals[fname] = {'model': model, 'ids': record_vals[fname]} if (model := record[field.model_field]) else False
                    else:
                        record_vals[fname] = {'model': co_records._name, 'ids': co_records._ids}
            elif field.type == 'monetary':
                currency_field = field.get_currency_field(self)
                if currency_field:
                    currency = self[currency_field]
                    for vals in vals_list:
                        vals[fname] = formatLang(self.env, vals[fname], currency_obj=currency)
            elif field.type == 'char' and field.name in self._ai_field_names_to_truncate():
                for vals in vals_list:
                    vals[fname] = self._ai_truncate(vals[fname])

        return vals_list, files_parts, files_checksums

    def _get_ai_context(self, field_paths):
        """ Get the json-encoded context dict for a record given a list of field paths.
        The context dict is a mini-orm snapshot with values formatted for LLM usage.
        It is a dictionary of the form:

        .. code-block:: python

            {
                "model_A": [
                    {
                        "id": 1,
                        "field_A": "val_1",
                        "field_B": {"model": "model_B", "ids": [3]},
                    },
                    {
                        "id": 2,
                        "field_A": "val_2",
                        "field_B": {"model": "model_B", "ids": [4]},
                    }
                ],
                "model_B": [
                    {
                        "id": 3,
                        "field_C": "val_3"
                    },
                    {
                        "id": 4,
                        "field_C": "val_4"
                    }
                ]
            }
        """
        self.ensure_one()
        models = {}

        def _map_to_models(records, path):
            model = records._name
            ids = OrderedSet(records._ids)
            if model not in models:
                models[model] = {'fields': OrderedSet(), 'ids': ids}
            else:
                models[model]['ids'] |= ids
            if not path:
                return
            fname = path[0]
            field = records._fields.get(fname)
            if not field:
                return
            if field.type in ('many2many', 'many2one', 'one2many'):
                _map_to_models(records[fname], path[1:])
            elif field.type == 'reference':
                for record in records:
                    if record[fname]:
                        _map_to_models(record[fname], path[1:])
            elif field.type == 'many2one_reference':
                for record in records:
                    if (ref_model := record[field.model_field]) and (ref_id := record[fname]):
                        _map_to_models(self.env[ref_model].browse(ref_id), path[1:])
            models[model]['fields'].add(fname)

        # get a mapping {model: {fields, ids}} to know which fields to read on which records
        for path in field_paths:
            _map_to_models(self, path.split("."))

        snapshot = {}
        files_parts = []  # files are sent separately to LLMs
        files_checksums = set()
        for model, info in models.items():
            records = self.env[model].browse(info['ids'])
            snapshot[model], files_parts, files_checksums = records._ai_read(list(info['fields']), files_parts, files_checksums)

        def _ai_context_json_default(obj):
            """NewId is not json serializable, use its string representation"""
            if isinstance(obj, NewId):
                return obj.origin or str(obj)
            return obj

        return json.dumps(snapshot, default=_ai_context_json_default, ensure_ascii=False), files_parts

    def _ai_format_records(self):
        """Format what will be in the prompt when we inserted records.

        It needs to return a dict which keys are the records ids, and
        the value of the dict can be anything.
        """
        return {record.id: record.display_name for record in self}

    def _process_html_fields(self, vals):
        """
        Scan values for HTML fields, parse them to find AI-inserted images,
        extract their attachment IDs to save them from the vacuum, and
        clean the `data-ai-channel-id` attribute from the HTML before saving.
        """
        if not vals:
            return

        # vals can contain keys that aren't fields on the model
        html_fields = [fname for fname in vals if vals[fname] and fname in self._fields and self._fields[fname].type == 'html']
        if not html_fields:
            return

        attachment_ids_to_mark = []
        for fname in html_fields:
            # Handle both single string and dict of translations
            value = vals[fname]
            is_dict = isinstance(value, dict)
            contents = value if is_dict else {None: value}

            for lang, html_content in contents.items():
                if not isinstance(html_content, str):
                    continue
                is_markup = isinstance(html_content, Markup)
                try:
                    root = html.fragment_fromstring(html_content, create_parent='div')
                except (ParserError, XMLSyntaxError):
                    continue

                for el in root.xpath('//img[@data-ai-channel-id]'):
                    att_id = el.get('data-attachment-id')
                    if att_id and att_id.isdigit():
                        attachment_ids_to_mark.append(int(att_id))

                    # Remove the attribute
                    del el.attrib['data-ai-channel-id']

                # Convert back to string and strip the temporary <div>...</div> wrapper
                # <div> is 5 chars, </div> is 6 chars.
                cleaned_html = html.tostring(root, encoding='unicode')[5:-6]
                if is_markup:
                    cleaned_html = Markup(cleaned_html)
                if is_dict:
                    value[lang] = cleaned_html
                else:
                    vals[fname] = cleaned_html

        if attachment_ids_to_mark:
            self.env['ai.attachment.vacuum'].mark_attachments_used(attachment_ids_to_mark)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._process_html_fields(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._process_html_fields(vals)
        return super().write(vals)

    def _ai_get_preview_metadata(self):
        """Build preview metadata list. To be overridden to add model-specific frontend fields."""
        return [
            {'id': record.id, 'preview_name': record.display_name}
            for record in self
        ]
