from odoo import api, fields, models


class PlanningSlotTemplate(models.Model):
    _inherit = 'planning.slot.template'

    worksheet_template_id = fields.Many2one(
        'worksheet.template',
        string="Worksheet",
        domain="[('res_model', '=', 'planning.slot'), '|', ('company_id', '=', False), ('company_id', '=?',  company_id)]",
        check_company=True,
    )

    @api.depends('worksheet_template_id')
    def _compute_company_id(self):
        super()._compute_company_id()

    @api.onchange('company_id')
    def _onchange_company_id_check_worksheet_template(self):
        if self.company_id and self.worksheet_template_id.company_id and self.company_id != self.worksheet_template_id.company_id:
            self.worksheet_template_id = False

    def _get_company(self):
        return self.worksheet_template_id.company_id

    def _get_display_name_fields(self):
        return super()._get_display_name_fields() + ['worksheet_template_id']

    def _get_extra_name_fields(self):
        fields = super()._get_extra_name_fields()
        if self.worksheet_template_id:
            fields.append('worksheet_template_id')
        return fields
