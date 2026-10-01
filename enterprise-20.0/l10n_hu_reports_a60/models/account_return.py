from odoo import fields, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_hu_reports_a60_first_name = fields.Char()
    l10n_hu_reports_a60_last_name = fields.Char()
    l10n_hu_reports_a60_phone_number = fields.Char()
    l10n_hu_reports_a60_contact_person = fields.Char()

    def _prepare_submission(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_hu_reports_a60.hu_a60_return_type':
            wizard = self.env['l10n_hu_reports_a60.ec.sales.list.submission.wizard']._open_submission_wizard(self)
            wizard['context']['dialog_size'] = 'medium'
            return wizard

        return super()._prepare_submission()

    def _generate_locking_attachments(self, options):
        # EXTENDS account_reports
        super()._generate_locking_attachments(options)
        if self.type_external_id == 'l10n_hu_reports_a60.hu_a60_return_type':
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'export_to_xml'))
