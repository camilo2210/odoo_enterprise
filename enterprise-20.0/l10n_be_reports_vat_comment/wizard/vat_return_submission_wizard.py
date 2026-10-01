from odoo import fields, models


class L10n_BeVatReturnSubmissionWizard(models.TransientModel):
    _inherit = "l10n_be_reports.vat.return.submission.wizard"

    comment = fields.Text()

    def _get_submission_options_to_inject(self):
        result = super()._get_submission_options_to_inject()
        if self.comment:
            result['comment'] = self.comment
        return result
