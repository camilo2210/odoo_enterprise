from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    totals_below_sections = fields.Boolean(related='company_id.totals_below_sections', string='Add totals below sections', readonly=False,
                                           help='When ticked, totals and subtotals appear below the sections of the report.')
    account_reports_negative_format = fields.Selection(
        related='company_id.account_reports_negative_format',
        string='Negative amount display',
        readonly=False,
        )
    account_return_periodicity = fields.Selection(related='company_id.account_return_periodicity', string='Periodicity', readonly=False, required=True)
    account_return_reminder_day = fields.Integer(related='company_id.account_return_reminder_day', string='Deadline', readonly=False, required=True)
    account_tax_return_journal_id = fields.Many2one(related='company_id.account_tax_return_journal_id', string='Journal', readonly=False)

    def open_tax_return_type_list(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('account_reports.action_view_account_return_types')
        action['domain'] = [
            ('category', '=', 'account_return'),
            '|', ('is_country_in_active_country', '=', True), ('country_id', '=', False),
        ]
        return action
