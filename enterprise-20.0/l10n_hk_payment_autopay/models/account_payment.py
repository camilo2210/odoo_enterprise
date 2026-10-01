# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_hk_autopay_account_type = fields.Selection(
        selection=[
            ('bban', 'Bank Code + Account Number + Beneficiary Name'),
            ('svid', 'FPS ID'),
            ('emal', 'Email address + / Bank Code'),
            ('mobn', '(Country Code) Mobile Phone Number + / Bank Code'),
            ('hkid', 'HKID + Beneficiary Name'),
        ],
        default='bban',
        string="AutoPay Account Type",
        required=True,
        help="Select the type of bank account details you are using for this payment.",
    )
    l10n_hk_autopay_account_proxy_id = fields.Char(
        string="AutoPay Account Proxy ID",
        help="Enter the proxy ID associated with the selected Payment Account Type.",
    )

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super()._get_method_codes_using_bank_account()
        res.append('l10n_hk_mri')
        return res
