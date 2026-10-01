from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class PosFiskalyDetailsWizard(models.TransientModel):
    _name = 'pos.fiskaly.details.wizard'
    _description = 'Point of Sale fiskaly Details Report'

    start_date = fields.Datetime(required=True, default=lambda self: fields.Datetime.now() - relativedelta(months=3))
    end_date = fields.Datetime(required=True, default=fields.Datetime.now)
    pos_config_ids = fields.Many2many('pos.config', string='Point of Sale', domain=[("company_id.l10n_at_fiskaly_organization_id", "!=", False)])

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            self.end_date = self.start_date

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            self.start_date = self.end_date

    def action_dep_audit_report(self):
        configs = self.pos_config_ids or self.env['pos.config'].search(self._check_company_domain(self.env.company))
        return configs.print_dep7_report(self.start_date, self.end_date)
