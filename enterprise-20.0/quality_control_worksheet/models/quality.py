# Part of Odoo. See LICENSE file for full copyright and licensing details.
from ast import literal_eval

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.fields import Domain


class QualityPoint(models.Model):
    _inherit = "quality.point"

    worksheet_template_id = fields.Many2one(
        'worksheet.template', 'Template', index='btree_not_null',
        domain="[('res_model', '=', 'quality.check'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    worksheet_success_conditions = fields.Char('Success Conditions')
    currency_id = fields.Many2one('res.currency', related='worksheet_template_id.currency_id')


class QualityCheck(models.Model):
    _inherit = "quality.check"

    worksheet_template_id = fields.Many2one(
        'worksheet.template', 'Quality Template', index='btree_not_null', precompute=True,
        domain="[('res_model', '=', 'quality.check'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        compute='_compute_worksheet_template_id', store=True, readonly=False)
    worksheet_properties = fields.Properties('Worksheet Properties', definition='worksheet_template_id.worksheet_properties_definition', copy=True)

    @api.depends('point_id')
    def _compute_worksheet_template_id(self):
        for check in self:
            if check.point_id and check.point_id.test_type == 'worksheet':
                check.worksheet_template_id = check.point_id.worksheet_template_id
            else:
                check.worksheet_template_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'point_id' in vals and not vals.get('worksheet_template_id'):
                point = self.env['quality.point'].browse(vals['point_id'])
                if point.test_type == 'worksheet':
                    vals['worksheet_template_id'] = point.worksheet_template_id.id
        return super().create(vals_list)

    def action_open_quality_check_wizard(self, current_check_id=None):
        check_ids = sorted(self.ids)
        check_id = self.browse(current_check_id or check_ids[0])
        if check_id.test_type == 'worksheet':
            # in this case the worksheet will pop up, while the wizard will be in the background
            # to prevent code duplication
            action = check_id.action_quality_worksheet()
            quality_wizard = self.env['quality.check.wizard'].create({
                'check_ids': check_ids,
                'current_check_id': check_id.id,
            })
            action['context'].update({
                'default_check_ids': check_ids,
                'default_current_check_id': check_id.id,
                'quality_wizard_id': quality_wizard.id,
                'from_failure_form': False,
            })
            return action
        return super().action_open_quality_check_wizard(current_check_id)

    def action_quality_worksheet(self):
        form_view_id = self.env.ref('quality_control_worksheet.quality_check_view_form_validate_worksheet').id
        action_name = self._get_check_action_name()
        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'res_model': 'quality.check',
            'res_id': self.id,
            'views': [(form_view_id, 'form')],
            'target': 'new',
            'context': {},
        }

    def action_worksheet_check(self):
        self.ensure_one()
        if not self.worksheet_template_id:
            raise UserError(_("Please fill in the worksheet."))
        domain = Domain(literal_eval(self.point_id.worksheet_success_conditions or '[]'))
        quality_wizard_id = self.env.context.get('quality_wizard_id')
        if quality_wizard_id:
            quality_wizard = self.env['quality.check.wizard'].browse(quality_wizard_id)
            if self.filtered_domain(domain):
                return quality_wizard.do_pass()
            else:
                # TODO: Write fail message ?
                return quality_wizard.do_fail()
        else:
            if self.filtered_domain(domain):
                return self.do_pass()
            else:
                return self.do_fail()

    def action_worksheet_discard(self):
        quality_wizard_id = self.env.context.get('quality_wizard_id')
        if quality_wizard_id:
            quality_wizard = self.env['quality.check.wizard'].browse(quality_wizard_id)
            return quality_wizard.action_generate_previous_window()
        return {'type': 'ir.actions.act_window_close'}

    def action_generate_next_window(self):
        quality_wizard_id = self.env.context.get('quality_wizard_id')
        if quality_wizard_id:
            quality_wizard = self.env['quality.check.wizard'].browse(quality_wizard_id)
            return quality_wizard.action_generate_next_window()
        return {'type': 'ir.actions.act_window_close'}

    def _get_props_formatted(self):
        for quality_check in self:
            if quality_check.worksheet_properties:
                properties_values = quality_check.worksheet_properties.field.convert_to_read(
                    quality_check.worksheet_properties._values,
                    quality_check.worksheet_properties.record,
                    use_display_name=False,
                )
                for prop in properties_values:
                    if prop['type'] == 'monetary':
                        prop['currency_field'] = self.currency_id
                return quality_check.worksheet_template_id.format_props(properties_values)
        return []

    def _is_pass_fail_applicable(self):
        return self.test_type == 'worksheet' and True or super()._is_pass_fail_applicable()
