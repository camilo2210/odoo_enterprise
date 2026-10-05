# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning
from odoo.tools import BinaryBytes


ACCOUNT_TYPE_MAPPING = {
    "regular": "1",
    "current": "2",
    "savings": "4",
    "other": "9",
}


class AccountBatchPayment(models.Model):
    _inherit = "account.batch.payment"

    l10n_jp_zengin_merge_transactions = fields.Boolean(
        string="Merge Transactions",
        help="Merge collective payments for Zengin files",
        compute="_compute_l10n_jp_zengin_merge_transactions",
        store=True, readonly=False,
    )

    @api.depends('journal_id')
    def _compute_l10n_jp_zengin_merge_transactions(self):
        for record in self:
            record.l10n_jp_zengin_merge_transactions = record.journal_id.l10n_jp_zengin_merge_transactions

    def _validate_bank_account_for_zengin(self, bank_account):
        partner = bank_account.partner_id
        missing_fields = []

        if not bank_account.bank_bic:
            missing_fields.append(self.env._("BIC"))
        if not bank_account.l10n_jp_zengin_bank_name_kana:
            missing_fields.append(self.env._("Bank name in Kana"))
        if not bank_account._get_clearing_number('JP'):
            missing_fields.append(self.env._("Zengin branch code"))
        if not bank_account.l10n_jp_zengin_branch_name_kana:
            missing_fields.append(self.env._("Branch name in Kana"))
        if not bank_account.l10n_jp_zengin_holder_name_kana:
            missing_fields.append(self.env._("Account holder name in Kana"))
        if not bank_account.l10n_jp_zengin_account_type:
            missing_fields.append(self.env._("Zengin account type"))

        if missing_fields:
            error_title = self.env._(
                "Following fields are missing for %(bank)s bank account of %(partner)s:\n",
                bank=bank_account.display_name,
                partner=partner.display_name,
            )
            action_error = {
                'view_mode': 'form',
                'res_model': 'res.partner.bank',
                'type': 'ir.actions.act_window',
                'res_id': bank_account.id,
                'views': [[self.env.ref('base.view_partner_bank_form').id, 'form']],
            }
            raise RedirectWarning(error_title + '\n'.join(missing_fields), action_error, self.env._("Go to Bank Account"))

    def _validate_sender_for_zengin(self):
        journal = self.journal_id
        bank_account = journal.bank_account_id
        self._validate_bank_account_for_zengin(bank_account)

        error_msgs = []
        if not bank_account.l10n_jp_zengin_client_code:
            error_msgs.append(_("Please set a client code on the %(account)s bank account for %(partner)s.", account=bank_account.display_name, partner=bank_account.partner_id.display_name))
        if bank_account.l10n_jp_zengin_account_type == 'savings':
            error_msgs.append(_("Savings account type is not supported for Zengin on %(account)s bank account for %(partner)s.", account=bank_account.display_name, partner=bank_account.partner_id.display_name))

        if error_msgs:
            action_error = {
                'view_mode': 'form',
                'res_model': 'res.partner.bank',
                'type': 'ir.actions.act_window',
                'res_id': bank_account.id,
                'views': [[self.env.ref('base.view_partner_bank_form').id, 'form']],
            }
            raise RedirectWarning('\n'.join(error_msgs), action_error, _("Go to Bank Account"))

    def _generate_zengin_header(self):
        transfer_date = self.date
        journal = self.journal_id
        bank_account = journal.bank_account_id
        return "".join([
            "1",                                                                  # Record type code
            "21",                                                                 # Type code: 21 General transfer
            "0",                                                                  # Code division
            f"{bank_account.l10n_jp_zengin_client_code:10.10}"                    # Company code
            f"{bank_account.l10n_jp_zengin_holder_name_kana:40.40}",              # Name of remittance requester (kana)
            transfer_date.strftime('%m%d'),                                       # Transfer date MMDD
            f"{bank_account.bank_bic:4.4}",                                       # Bank code
            f"{bank_account.l10n_jp_zengin_bank_name_kana:15.15}",                # Bank name (Kana)
            f"{bank_account._get_clearing_number('JP'):3.3}",                     # Branch Code
            f"{bank_account.l10n_jp_zengin_branch_name_kana:15.15}",              # Branch name (Kana)
            f"{ACCOUNT_TYPE_MAPPING[bank_account.l10n_jp_zengin_account_type]}",  # Subjects: 1: Regular, 2: Current, 4: Saving, 9: Other
            f"{bank_account.account_number:7.7}",                                 # Account Number
            f"{'':17}"                                                            # Dummy
        ])

    def _generate_zengin_entry_detail(self, payments):
        bank_account = payments.partner_bank_id
        return "".join([
            "2",                                                                    # Record type code
            f"{bank_account.bank_bic:4.4}",                                         # Bank code
            f"{bank_account.l10n_jp_zengin_bank_name_kana:15.15}",                  # Bank name (Kana)
            f"{bank_account._get_clearing_number('JP'):3.3}",                       # Branch code
            f"{bank_account.l10n_jp_zengin_branch_name_kana:15.15}",                # Branch name (Kana)
            "0000",                                                                 # Clearing house code
            f"{ACCOUNT_TYPE_MAPPING[bank_account.l10n_jp_zengin_account_type]}",    # Subjects: 1: Regular, 2: Current, 4: Saving, 9: Other
            f"{bank_account.account_number:7.7}",                                   # Account number
            f"{bank_account.l10n_jp_zengin_holder_name_kana:30.30}",                # Name of remittance requester (kana)
            f"{int(sum(payments.mapped('amount'))):0>10d}",                         # Amount
            "0",                                                                    # New Code, 0: Other
            "0000000000"                                                            # Customer code 1
            "0000000000"                                                            # Customer code 2
            "7",                                                                    # Transfer designation category (* Regardless of the transfer category, Web21 will handle it as a "7. telegraphic transfer.)
            " ",                                                                    # Identification code (Optional item therefore can be left blank)
            f"{'':7}"                                                               # Dummy
        ])

    def _generate_zengin_trailer(self, record_count, payments):
        return "".join([
            "8",                                             # Record Type Code
            f"{record_count:0>6d}",                          # Total number of records
            f"{int(sum(payments.mapped('amount'))):0>12d}",  # Total amount
            f"{'':101}"                                      # Dummy
        ])

    def _generate_zengin_footer(self):
        return "".join([
            "9",         # Record Type Code
            f"{'':119}"  # Dummy
        ])

    def _generate_zengin_file(self):
        entries = [self._generate_zengin_header()]

        grouped_payments = self.payment_ids.grouped("partner_bank_id")
        record_count = 0
        for partner_bank_id, payments in grouped_payments.items():
            self._validate_bank_account_for_zengin(partner_bank_id)
            if self.l10n_jp_zengin_merge_transactions:
                entries.append(self._generate_zengin_entry_detail(payments))
                record_count += 1
            else:
                entries.extend([self._generate_zengin_entry_detail(payment) for payment in payments])
                record_count += len(payments)

        entries.extend([
            self._generate_zengin_trailer(record_count, self.payment_ids),
            self._generate_zengin_footer()
        ])

        return "\r\n".join(entries)

    def _get_methods_generating_files(self):
        res = super()._get_methods_generating_files()
        res.append("zengin")
        return res

    def _generate_export_file(self):
        if self.payment_method_code == "zengin":
            self._validate_sender_for_zengin()
            data = self._generate_zengin_file()
            date = fields.Datetime.today().strftime("%Y-%m-%d")  # JP date format
            return {
                "file": BinaryBytes(data.encode(encoding="Shift_JIS")),
                "filename": f"ZENGIN-{self.journal_id.code}-{date}.txt",
            }
        else:
            return super()._generate_export_file()
