# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10n_UkHmrcSendWizard(models.TransientModel):
    _name = 'l10n_uk.hmrc.send.wizard'
    _description = "HMRC Send Wizard"

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if any(key not in self.env.context for key in ['client_data', 'return_id']):
            return res

        # Check obligations: should be logged in by now
        self.env['l10n_uk.vat.obligation'].import_vat_obligations()

        if 'obligation_id' in fields:
            obligations = self.env['l10n_uk.vat.obligation'].search([('status', '=', 'open')])
            if not obligations:
                raise UserError(self.env._('No open VAT obligations were found on HMRC. '
                    'You can manually mark the return as completed or archive it if no further action is required.'))

            return_record = self.env['account.return'].browse(self.env.context['return_id'])
            for obl in obligations:
                if obl.date_start == return_record.date_from and obl.date_end == return_record.date_to:
                    res['obligation_id'] = obl.id
                    break

        if 'hmrc_gov_client_device_id' in fields:
            res['hmrc_gov_client_device_id'] = self.env.context['client_data']['hmrc_gov_client_device_id']

        if 'message' in fields:
            res['message'] = not res.get('obligation_id')
        return res

    obligation_id = fields.Many2one('l10n_uk.vat.obligation', 'Obligation', domain=[('status', '=', 'open')], required=True)
    message = fields.Boolean('Message', readonly=True) # Show message if no obligation corresponds to report options
    accept_legal = fields.Boolean('Accept Legal Statement') # A checkbox to warn the user that what he sends is legally binding
    hmrc_gov_client_device_id = fields.Char(default=lambda x: uuid.uuid4())
