import json

from odoo import api, fields, models


class L10nHUIntrastatGoodsSubmissionWizard(models.TransientModel):
    _name = 'l10n_hu_intrastat.intrastat.goods.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Intrastat Goods Submission Wizard"

    l10n_hu_intrastat_contact_executive = fields.Many2one(comodel_name='res.partner', help="The executive approving Intrastat file submissions")
    l10n_hu_intrastat_contact_executive_status = fields.Char(help="Job position of the executive approving Intrastat file submissions")
    l10n_hu_intrastat_contact_person = fields.Many2one(comodel_name='res.partner', help="Contact person for the Intrastat file submissions")

    @api.model
    def _l10n_hu_intrastat_open_submission_wizard(self, account_return, instructions=None, contact_executive=None, contact_executive_status=None, contact_person=None):
        record_action = self._open_submission_wizard(account_return, instructions)
        wizard = self.env['l10n_hu_intrastat.intrastat.goods.submission.wizard'].browse(record_action['res_id'])
        vals = {
            field: value
            for field, value in [
                ('l10n_hu_intrastat_contact_executive', contact_executive),
                ('l10n_hu_intrastat_contact_executive_status', contact_executive_status),
                ('l10n_hu_intrastat_contact_person', contact_person),
            ] if value
        }
        if vals:
            wizard.write(vals)
        return wizard._get_records_action(target='new', name=record_action['name'])

    def print_csv(self):
        options = self.return_id._get_closing_report_options()
        options['l10n_hu_intrastat_goods_submission_wizard_id'] = self.id

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'hu_intrastat_export_to_csv',
                'no_closing_after_download': True,
            }
        }
