from odoo import api, fields, models


class L10n_hu_ReportsEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_hu_reports_a60.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "EC Sales List Submission Wizard"

    first_name = fields.Char(string="First Name", compute="_compute_default_values", store=True, readonly=False)
    last_name = fields.Char(string="Last Name", compute="_compute_default_values", store=True, readonly=False)
    phone_number = fields.Char(string="Phone Number", compute="_compute_default_values", store=True, readonly=False)
    contact_person = fields.Char(string="Contact Person", compute="_compute_default_values", store=True, readonly=False)

    @api.depends('return_id')
    def _compute_default_values(self):
        for wizard in self:
            account_return = wizard.return_id
            last_return = account_return.search_fetch([
                ('type_id', '=', account_return.type_id.id),
                ('date_to', '<', account_return.date_from),
            ], field_names=[
                'l10n_hu_reports_a60_first_name',
                'l10n_hu_reports_a60_last_name',
                'l10n_hu_reports_a60_phone_number',
                'l10n_hu_reports_a60_contact_person',
            ], order='date_to desc', limit=1)

            wizard.first_name = last_return.l10n_hu_reports_a60_first_name
            wizard.last_name = last_return.l10n_hu_reports_a60_last_name
            wizard.phone_number = last_return.l10n_hu_reports_a60_phone_number
            wizard.contact_person = last_return.l10n_hu_reports_a60_contact_person

    def action_proceed_with_submission(self):
        self.ensure_one()
        self.return_id.write({
            'l10n_hu_reports_a60_first_name': self.first_name,
            'l10n_hu_reports_a60_last_name': self.last_name,
            'l10n_hu_reports_a60_phone_number': self.phone_number,
            'l10n_hu_reports_a60_contact_person': self.contact_person,
        })
        return self.return_id._proceed_with_submission()

    def download_xml(self):
        attachment = self.return_id.attachment_ids.filtered_domain([
            ('res_model', '=', 'account.return'),
            ('res_name', '=', self.return_id.name),
            ('mimetype', '=', 'application/xml'),
        ])
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
