# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import json
from lxml import etree
from markupsafe import Markup

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.safe_eval import expr_eval


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _domain_worksheet_template_id(self):
        return self.env['worksheet.template'].search([('res_model', '=', 'planning.slot')], limit=1)

    has_studio_worksheet_fields = fields.Boolean(compute="_compute_has_studio_worksheet_fields")
    worksheet_template_id = fields.Many2one(
        'worksheet.template', string="Worksheet",
        tracking=15,
        default=lambda self: self._domain_worksheet_template_id(),
        group_expand='_group_expand_worksheet_template_id',
        domain="[('res_model', '=', 'planning.slot'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Create templates for each type of intervention you have and customize their content with your own custom fields.",
        check_company=True,
    )
    worksheet_properties = fields.Properties('Worksheet Properties', definition='worksheet_template_id.worksheet_properties_definition', copy=True)
    photo_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'planning.slot'), ('mimetype', '=like', 'image/%')],
        string='Photos',
        copy=False,
    )

    @api.depends('worksheet_template_id')
    def _compute_show_customer_preview(self):
        super()._compute_show_customer_preview()

    @api.depends('worksheet_template_id')
    def _compute_template_autocomplete_ids(self):
        super()._compute_template_autocomplete_ids()

    @api.depends('worksheet_template_id')
    def _compute_template_id(self):
        super()._compute_template_id()

    @api.depends('worksheet_template_id')
    def _compute_allow_template_creation(self):
        super()._compute_allow_template_creation()

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id.worksheet_template_id:
            self.worksheet_template_id = self.template_id.worksheet_template_id

    def _is_node_invisible(self, xml_node, record_data):
        current_node = xml_node
        while current_node is not None and current_node.tag in ('field', 'group', 'page'):
            cond = current_node.get('invisible')
            if modifiers := current_node.get('modifiers'):
                cond = json.loads(modifiers).get('invisible', cond)
            if isinstance(cond, str):
                cond = cond.strip()
                if cond == 'True' or (cond.startswith('[') and self.filtered_domain(ast.literal_eval(cond))) or (not cond.startswith('[') and expr_eval(cond, record_data)):
                    return True
            elif isinstance(cond, list) and self.filtered_domain(cond):
                return True
            current_node = current_node.getparent()
        return False

    def _get_props_formatted(self, readonly=False):
        self.ensure_one()
        formatted_properties = []
        if self.worksheet_properties:
            properties_values = self.worksheet_properties.field.convert_to_read(
                self.worksheet_properties._values,
                self.worksheet_properties.record,
                use_display_name=False,
            )
            for prop in properties_values:
                if prop['type'] == 'monetary':
                    prop['currency_field'] = self._get_currency_field()
            for prop in self.worksheet_template_id.format_props(properties_values):
                if prop['type'] == 'boolean':
                    prop['readonly'] = readonly
                formatted_properties.append(prop)
        worksheet_page = etree.fromstring(self.env['planning.slot'].get_view(view_type='form')['arch']).xpath("//page[@name='worksheet']")
        if worksheet_page:
            record_dict = self.read()[0]
            record_data = {k: (v[0] if isinstance(v, tuple) else v) for k, v in record_dict.items()}
            for node in worksheet_page[0].xpath('.//group[not(ancestor::group) and not(ancestor::field)] | .//field[not(ancestor::group) and not(ancestor::field)]'):
                if self._is_node_invisible(node, record_data):
                    continue
                if node.tag == 'field':
                    f_data = self._extract_studio_field_data(node, record_dict)
                    if f_data:
                        formatted_properties.append(f_data)
                else:
                    cols = node.xpath('./group')
                    if cols and len(cols) > 1:
                        col_data = []
                        for col in cols:
                            if self._is_node_invisible(col, record_data):
                                continue
                            fields_in_col = [f for f in (self._extract_studio_field_data(fn, record_dict) for fn in col.xpath('.//field[not(ancestor::field)]') if not self._is_node_invisible(fn, record_data)) if f]
                            if fields_in_col:
                                col_data.append(fields_in_col)
                        if col_data:
                            formatted_properties.append({
                                'type': 'studio_columns',
                                'columns': col_data
                            })
                    else:
                        fields_in_group = [f for f in (self._extract_studio_field_data(fn, record_dict) for fn in node.xpath('.//field[not(ancestor::field)]') if not self._is_node_invisible(fn, record_data)) if f]
                        for f_data in fields_in_group:
                            if f_data:
                                formatted_properties.append(f_data)
        return formatted_properties

    def _extract_studio_field_data(self, xml_node, record_dict):
        field_name = xml_node.get('name')
        if not field_name or field_name not in self._fields or field_name == 'worksheet_properties':
            return None
        field_def = self._fields[field_name]
        field_value = record_dict.get(field_name)
        prop_type = field_def.type
        if prop_type == 'binary':
            if xml_node.get('widget') in ('image', 'signature'):
                prop_type = 'signature'
                if isinstance(field_value, dict):
                    field_value = field_value.get('content', '')
            else:
                prop_type = 'binary'
                if field_value:
                    field_value = {
                        'field': field_name,
                        'filename': record_dict.get(f"{field_name}_filename", "Download File")
                    }
        elif isinstance(field_value, tuple):
            field_value = field_value[1]
        elif prop_type == 'text' and field_value:
            field_value = Markup('<br>\n').join(field_value.split('\n'))
        elif prop_type == 'selection' and field_value is not False:
            selection = field_def.selection
            if isinstance(selection, (list, tuple)):
                field_value = dict(selection).get(field_value, field_value)
        elif prop_type in ('one2many', 'many2many'):
            if field_value:
                records = self[field_name]
                if xml_node.get('widget') == 'many2many_tags':
                    prop_type = 'tags'
                    field_value = [{'name': r.display_name, 'style': ''} for r in records]
                else:
                    prop_type = 'char'
                    field_value = ", ".join(records.mapped('display_name'))
            else:
                field_value = ""
        return {
            'name': xml_node.get('string') or field_def.string,
            'type': prop_type,
            'value': field_value if field_value is not False else "",
            'readonly': True
        }

    def _get_currency_field(self):
        return self.worksheet_template_id.currency_id

    def _is_intervention_report_available(self):
        return super()._is_intervention_report_available() or (self.worksheet_template_id and any(self.worksheet_properties.values()) or self.has_studio_worksheet_fields)

    def _get_is_intervention_report_available_domain(self):
        return Domain([('worksheet_template_id', '!=', False)])

    def _group_expand_worksheet_template_id(self, worksheet_templates, domain):
        domain = Domain(domain)
        dom_tuples = [(cond.field_expr, cond.operator) for cond in domain.iter_conditions()]
        if ('start_datetime', '<') in dom_tuples and ('end_datetime', '>') in dom_tuples:
            if ('worksheet_template_id', '=') in dom_tuples or ('worksheet_template_id', 'ilike') in dom_tuples:
                filter_domain = self._expand_domain_m2o_groupby(domain, 'worksheet_template_id')
                return self.env['worksheet.template'].search(filter_domain)
            filters = Domain.AND([[('worksheet_template_id.active', '=', True)], self._expand_domain_dates(domain)])
            return self.env['planning.slot'].search(filters).mapped('worksheet_template_id')
        return worksheet_templates

    def _reset_intervention_fields(self):
        self.worksheet_template_id = False
        super()._reset_intervention_fields()

    def _prepare_template_values(self):
        return {
            **super()._prepare_template_values(),
            'worksheet_template_id': self.worksheet_template_id.id,
        }

    def _get_template_fields(self):
        return {
            **super()._get_template_fields(),
            'worksheet_template_id': 'worksheet_template_id',
        }

    def _get_domain_template_slots(self):
        domain = super()._get_domain_template_slots()
        if self.worksheet_template_id:
            domain = Domain.AND([
                domain,
                [('worksheet_template_id', 'in', [False, self.worksheet_template_id.id])],
            ])
        return domain

    def _get_unplanned_slot_values(self):
        return {
            **super()._get_unplanned_slot_values(),
            'worksheet_template_id': self.worksheet_template_id.id,
        }

    def _compute_has_studio_worksheet_fields(self):
        for slot in self:
            slot.has_studio_worksheet_fields = any(f.startswith('x_studio_') for f in slot._fields)
