# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import models, fields, _, api
from markupsafe import escape
from odoo.exceptions import ValidationError, UserError
from odoo.tools import SQL


class WorksheetTemplate(models.Model):
    _name = 'worksheet.template'
    _description = 'Worksheet template using properties field'
    _order = 'sequence, name'
    # This model is meant to be inherited in order to be used with the correct associated res_model

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    worksheet_properties_definition = fields.PropertiesDefinition('Worksheet Properties')
    company_id = fields.Many2one('res.company', string='Company', domain=lambda self: [('id', 'in', self.env.companies.ids)])
    active = fields.Boolean(default=True)
    res_model = fields.Char('Host Model', help="The model that is using this template")
    worksheet_count = fields.Integer(compute='_compute_worksheet_count')

    # field needed to enable the monetary field of properties
    currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_currency_id', compute_sql='_compute_currency_id', compute_sudo=True)

    @api.depends_context('company')
    @api.depends('company_id')
    def _compute_currency_id(self):
        default_currency_id = self.env.company.currency_id
        for template in self:
            template.currency_id = template.company_id.currency_id or default_currency_id

    def _compute_sql_currency_id(self, table):
        return SQL("COALESCE(%s, %s)", table.company_id.currency_id, self.env.company.currency_id.id)

    def _compute_worksheet_count(self):
        models_to_check = {model for pairs in self._get_models_to_check_dict().values() for model, _name in pairs}
        counts = defaultdict(int)
        for model in models_to_check:
            for template, count in self.env[model]._read_group(
                [('worksheet_template_id', 'in', self.ids)],
                ['worksheet_template_id'],
                ['__count'],
            ):
                counts[template.id] += count

        for template in self:
            template.worksheet_count = counts[template.id]

    @api.constrains('res_model')
    def _check_res_model_exists(self):
        res_models = self.mapped('res_model')
        ir_model_names = [res['model'] for res in self.env['ir.model'].sudo().search_read([('model', 'in', res_models)], ['model'])]
        if any(model_name not in ir_model_names for model_name in res_models):
            raise ValidationError(_('The host model name should be an existing model.'))

    def write(self, vals):
        old_company_id = self.company_id
        res = super().write(vals)
        if 'company_id' in vals and self.company_id:
            update_company_id = old_company_id - self.company_id
            template_dict = defaultdict(lambda: self.env['worksheet.template'])
            for template in self:
                template_dict[template.res_model] |= template
            for res_model, templates in template_dict.items():
                for model, _name in self._get_models_to_check_dict()[res_model]:
                    records = self.env[model].search([('worksheet_template_id', 'in', templates.ids)])
                    for record in records:
                        if record.company_id not in record.worksheet_template_id.company_id:
                            if update_company_id:
                                company_name = update_company_id.mapped('name')
                                raise UserError(_("Unfortunately, you cannot unlink this worksheet template from %s because the template is still connected to tasks within the company.", company_name))
                            else:
                                company_name = record.worksheet_template_id.company_id.mapped('name')
                                raise UserError(_("You can't restrict this worksheet template to '%(selected_company)s' because it's still connected to tasks in '%(tasks_company)s' (and potentially other companies). Please either unlink those tasks from this worksheet template, "
                                                  "move them to a project for the right company, or keep this worksheet template open to all companies.", selected_company=company_name, tasks_company=record.company_id.name))
        return res

    @api.model
    def _get_models_to_check_dict(self):
        """To be override in the module using it. It returns a dictionary contains
        the model you want to check for multi-company in the write method.
        Key: res_model name, eg: "quality.check"
        Value: a list of (model name, model name to show), eg: [("quality.point", "Quality Point"), ("quality.check", "Quality Check")]
        """
        return {}

    def format_props(self, property_values):
        tags_style_per_id = [
            'background-color:rgb(255, 155.5, 155.5);',  # default background if something goes wrong with the tags definition
            'background-color:rgb(255, 155.5, 155.5);',
            'background-color:rgb(247.0375, 198.06116071, 152.4625);',
            'background-color:rgb(252.88960843, 226.89175248, 135.61039157);',
            'background-color:rgb(187.45210396, 215.03675558, 248.04789604);',
            'background-color:rgb(216.79194664, 167.70805336, 203.91748283);',
            'background-color:rgb(247.84539474, 213.9484835, 199.65460526);',
            'background-color:rgb(136.6125, 224.8875, 218.94591346);',
            'background-color:rgb(150.60535714, 165.68382711, 248.89464286);',
            'background-color:rgb(254.94583333, 157.55416667, 203.95543194);',
            'background-color:rgb(182.62075688, 236.87924312, 189.81831118);',
            'background-color:rgb(230.11575613, 219.41069277, 252.08930723);',
        ]
        properties_formatted = []
        section_is_folded = False
        for prop in property_values:
            model = 'ir.qweb.field.' + prop['type']
            value = False
            if prop['type'] == 'separator':
                section_is_folded = prop['value'] if 'value' in prop else prop['fold_by_default']
            elif 'value' in prop:
                if prop['type'] == 'selection':
                    for selection in prop['selection']:
                        if selection[0] == prop['value']:
                            value = escape(selection[1] or '')
                            break
                elif prop['type'] in ['many2many', 'many2one']:
                    records = self.env[prop['comodel']].sudo().browse(prop['value'])
                    value = self.env[model].value_to_html(records, {})
                elif prop['type'] == 'float':
                    # The precision of the float type in properties is limited to 2
                    value = self.env[model].value_to_html(prop['value'], {'precision': 2})
                elif prop['type'] == 'monetary':
                    value = self.env[model].value_to_html(prop['value'], {'display_currency': prop['currency_field']})
                elif model in self.env:
                    value = self.env[model].value_to_html(prop['value'], {})
                elif prop['type'] in ['signature', 'boolean']:
                    value = prop['value']
                elif prop['type'] == 'tags':
                    dict_color_id_per_name = {}
                    value = []
                    for tag in prop['tags']:
                        dict_color_id_per_name[tag[1]] = tag[2]
                    for tag_name in prop['value']:
                        value.append({'name': tag_name, 'style': tags_style_per_id[dict_color_id_per_name.get(tag_name, 0)]})
                elif prop['type'] == 'char':
                    value = self.env['ir.qweb.field.text'].value_to_html(prop['value'], {})

            if not section_is_folded:
                prop_property = {'type': prop['type'], 'name': prop['string'], 'value': value}
                if prop['type'] == 'boolean':
                    prop_property['readonly'] = prop.get('readonly', False)
                properties_formatted.append(prop_property)
        return properties_formatted
