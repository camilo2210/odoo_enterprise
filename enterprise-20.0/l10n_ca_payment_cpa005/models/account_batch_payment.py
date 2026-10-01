# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, RedirectWarning
from odoo.tools import BinaryBytes, remove_accents

from odoo.addons.l10n_ca_payment_cpa005.models.res_partner_bank import (
    cpa005_sanitize_account_number,
    cpa005_sanitize_financial_institution_nr,
)


class AccountBatchPayment(models.Model):
    _inherit = "account.batch.payment"

    l10n_ca_cpa005_file_creation_number = fields.Char(
        string="File Creation Number used in Canadian EFT",
        copy=False,
        help="Leave blank to auto-populate with the next number in the sequence. The FCN is a 4-digit sequence from 0001 "
        "to 9999. This will be used by your bank to identify the file. You can set a value here to override the FCN "
        "sequence just for this payment.",
    )

    @api.constrains('payment_ids', 'payment_method_id')
    def _check_l10n_ca_cpa005_payments(self):
        for batch in self.filtered(lambda b: b.payment_method_code == 'cpa005' and b.payment_ids):
            batch._l10n_ca_cpa005_pre_validate()

    def _l10n_ca_cpa005_pre_validate(self):
        self.ensure_one()
        if self.payment_method_code != 'cpa005' or not self.payment_ids:
            return
        journal = self.journal_id

        # Company
        if not journal.company_id.l10n_ca_cpa005_short_name:
            raise RedirectWarning(
                self.env._("Please set a Canadian EFT short company name on the %s company.", journal.company_id.display_name),
                journal.company_id._get_records_action(),
                self.env._("Go to company"),
            )

        # Journal
        journal_errors = []
        if not journal.l10n_ca_cpa005_originator_id:
            journal_errors.append(self.env._("- Please set an originator ID."))
        if not journal.l10n_ca_cpa005_destination_data_center:
            journal_errors.append(self.env._("- Please set a destination data center."))
        elif len(journal.l10n_ca_cpa005_destination_data_center) != 5 or not journal.l10n_ca_cpa005_destination_data_center.isdigit():
            journal_errors.append(self.env._("- The destination data center must be a 5-digit numeric value."))
        if not journal.bank_account_id:
            journal_errors.append(self.env._("- Please set a Bank Account on the journal configuration."))
        if journal_errors:
            raise RedirectWarning(
                self.env._(
                    "Please fix the following issue(s) on the %(journal)s journal:\n%(errors)s",
                    journal=journal.display_name,
                    errors='\n'.join(journal_errors),
                ),
                journal._get_records_action(),
                self.env._("Go to journal"),
            )

        # Company bank account
        journal_bank_account_errors = []
        journal_bank_account = journal.bank_account_id
        if not journal_bank_account.allow_out_payment:
            journal_bank_account_errors.append(
                self.env._("- The company bank account needs to be trusted.")
            )
        if not journal_bank_account.l10n_ca_financial_institution_number:
            journal_bank_account_errors.append(
                self.env._("- The Financial Institution ID Number on the company bank account needs to be set."),
            )
        if not cpa005_sanitize_account_number(journal_bank_account.account_number):
            journal_bank_account_errors.append(
                self.env._("- The company bank account number must be only digits and at most 12 digits.")
            )
        if journal_bank_account_errors:
            raise RedirectWarning(
                self.env._(
                    "Please fix the following issue(s) on the company bank account set on %(journal)s journal:\n%(errors)s",
                    journal=journal.display_name,
                    errors='\n'.join(journal_bank_account_errors),
                ),
                journal_bank_account._get_records_action(),
                self.env._("Go to Bank Account"),
            )

    def validate_batch(self, initiate_payment=False):
        self._l10n_ca_cpa005_pre_validate()
        return super().validate_batch(initiate_payment=initiate_payment)

    def check_payments_for_errors(self):
        # EXTENDS 'account_batch_payment'
        rslt = super().check_payments_for_errors()
        if self.payment_method_code != 'cpa005':
            return rslt

        if invalid_bank_accounts_payments := self.payment_ids.filtered(lambda p:
            not cpa005_sanitize_account_number(p.partner_bank_id.account_number)
            or not cpa005_sanitize_account_number(p.return_partner_bank_id.account_number)
        ):
            rslt.append({
                'title': self.env._("Some bank accounts cannot be encoded in a Canadian CPA 005 file."),
                'records': invalid_bank_accounts_payments,
                'help': self.env._("Bank account of both the payor and the payee must be set and made of at most 12 digits."),
            })
        if invalid_financial_institution_payments := self.payment_ids.filtered(lambda p:
            not cpa005_sanitize_financial_institution_nr(p.partner_bank_id.l10n_ca_financial_institution_number)
            or not cpa005_sanitize_financial_institution_nr(p.return_partner_bank_id.l10n_ca_financial_institution_number)
        ):
            rslt.append({
                'title': self.env._("Some bank accounts cannot be encoded in a Canadian CPA 005 file."),
                'records': invalid_financial_institution_payments,
                'help': self.env._("Bank account's financial institution of both the payor and the payee must be set and made of 9 digits."),
            })

        if self.batch_type == 'inbound':
            # Due Date window for Record D (Standard 005 - Data Element Dictionary, "Due Date"):
            # it may not be post-dated more than 2 business days after the file date, nor more than
            # 173 calendar days before it, otherwise the bank will reject the transaction.
            out_of_window = self.payment_ids.filtered(lambda p: (
                (self.date - p.date).days > 173
                or self._l10n_ca_cpa005_business_days_count(self.date, p.date) > 2
            ))
            if out_of_window:
                rslt.append({
                    'title': self.env._("Some due (collection) dates are outside the window allowed by CPA 005."),
                    'records': out_of_window,
                    'help': self.env._(
                        "The due date must be no more than 2 business days after the file date (%(file_date)s) "
                        "and no more than 173 days before it.",
                        file_date=self.date,
                    ),
                })

        payments_without_tx_code = self.payment_ids.filtered(lambda p: not p.l10n_ca_cpa005_transaction_code_id)
        if payments_without_tx_code:
            rslt.append({
                'title': self.env._("Some payments have no EFT/CPA transaction code."),
                'records': payments_without_tx_code,
                'help': self.env._("Every payment initiated through the Canadian EFT service must carry a valid CPA code."),
            })

        return rslt

    def _l10n_ca_cpa005_get_counterparty_bank(self, payment):
        """ The payee or payor depending on the record type, always the "external" res.partner of the payment. """
        return payment.return_partner_bank_id if self.batch_type == 'inbound' else payment.partner_bank_id

    def _l10n_ca_cpa005_get_company_bank(self, payment):
        """ The bank account rejected file items get routed back to: always the company's own account,
        which sits on partner_bank_id for inbound payments and return_partner_bank_id for outbound ones.
        """
        return payment.partner_bank_id if self.batch_type == 'inbound' else payment.return_partner_bank_id

    def _l10n_ca_cpa005_business_days_count(self, start, end):
        """Count the business days (Monday-Friday, holidays not considered) from ``start`` to ``end``.
        The result is negative when ``end`` precedes ``start``.
        """
        if start == end:
            return 0
        step = 1 if end > start else -1  # count onward or backward
        count = 0
        current = start
        while current != end:
            current += timedelta(days=step)
            if current.weekday() < 5:  # Monday-Friday
                count += step
        return count

    def _l10n_ca_cpa005_get_currency(self):
        batch_currency = self.payment_ids.mapped("currency_id")

        if len(batch_currency) != 1:
            raise ValidationError(
                _(
                    "A Canadian EFT file can not contain multiple currencies (%s).",
                    ", ".join(batch_currency.mapped("display_name")),
                )
            )

        if batch_currency.name not in ('CAD', 'USD'):
            raise ValidationError(
                _(
                    "A Canadian EFT file can not contain %s. It can contain either exclusively payments "
                    "in Canadian dollars or exclusively payments in United States dollars.",
                    batch_currency.display_name,
                )
            )

        return batch_currency

    def _l10n_ca_cpa005_get_total_cents(self, payments):
        return sum(round(payment.amount * 100) for payment in payments)

    def _l10n_ca_cpa005_generate_header(self, currency, file_creation_nr):
        return remove_accents(
            "A"  # 01 1 1 "A" Logical Record Type ID
            "000000001"  # 02 2-10 9 "000000001" Logical Record Count
            f"{self.journal_id.l10n_ca_cpa005_originator_id:10.10}"  # 03 11-20 10 Alphanumeric Originator's ID
            f"{file_creation_nr:0>4.4}"  # 04 21-24 4 Numeric File Creation No.
            f"{self.date.strftime('%y%j'):0>6.6}"  # 05 25-30 6 Numeric Creation Date
            f"{self.journal_id.l10n_ca_cpa005_destination_data_center:0>5.5}"  # 06 31-35 5 Numeric Destination Data Centre
            f"{' ':20}"  # 07 36-55 20 Alphanumeric Reserved Customer-Direct Clearer Communication area
            f"{currency.name:3.3}"  # 08 56-58 3 Alphanumeric Currency Code Identifier
            f"{' ':1406}"  # 09 59-1464 1406 Alphanumeric Filler
        )

    def _l10n_ca_cpa005_transaction_record(self, file_creation_nr, payment, logical_record_count):
        journal = self.journal_id
        # Record type "C" for outbound credits (Direct Deposit) and "D" for inbound debits (Pre-Authorized Debit)
        record_type = 'D' if self.batch_type == 'inbound' else 'C'
        # The payee or payor depending on the record type, always the "external" res.partner
        counterparty_bank = self._l10n_ca_cpa005_get_counterparty_bank(payment)
        counterparty_account = cpa005_sanitize_account_number(counterparty_bank.account_number)
        counterparty_account_fin_inst_nr = cpa005_sanitize_financial_institution_nr(counterparty_bank.l10n_ca_financial_institution_number)
        # The "returns" bank account is the **originator** bank account, the account that generates this file, so always the res.company's
        originator_bank = self._l10n_ca_cpa005_get_company_bank(payment)
        originator_account = cpa005_sanitize_account_number(originator_bank.account_number)
        originator_account_fin_inst_nr = cpa005_sanitize_financial_institution_nr(originator_bank.l10n_ca_financial_institution_number)

        return remove_accents(  # ElementNumber CharacterPosition ElementSize ElementName
            f"{record_type}"  # 01 1 1 "C"/"D" Logical Record Type ID
            f"{logical_record_count:09d}"  # 02 2-10 9 Numeric Logical Record Count
            f"{journal.l10n_ca_cpa005_originator_id:10.10}{file_creation_nr:0>4.4}"  # 03 11-24 14 Alphanumeric Origination Control Data (originator ID + Numeric File Creation No.)
            f"{payment.l10n_ca_cpa005_transaction_code_id.code:0>3.3}"  # 04 25-27 3 Numeric Transaction Type
            f"{self._l10n_ca_cpa005_get_total_cents(payment):010d}"  # 05 28-37 10 Numeric Amount
            f"{payment.date.strftime('%y%j'):0>6.6}"  # 06 38-43 6 Numeric Date Funds to be Available
            f"{counterparty_account_fin_inst_nr:0>9.9}"  # 07 44-52 9 Numeric Institutional Identification No.
            f"{counterparty_account:12.12}"  # 08 53-64 12 Alphanumeric Payee Account No.
            f"{payment.id:022d}"  # 09 65-86 22 Numeric Item Trace No.
            f"{0:03d}"  # 10 87-89 3 Numeric Stored Transaction Type (RBC says to zero-fill)
            f"{journal.company_id.l10n_ca_cpa005_short_name:15.15}"  # 11 90-104 15 Alphanumeric Originator's Short Name
            f"{payment.partner_id.name:30.30}"  # 12 105-134 30 Alphanumeric Payee Name
            f"{journal.company_id.name:30.30}"  # 13 135-164 30 Alphanumeric Originator's Long Name
            f"{journal.l10n_ca_cpa005_originator_id:10.10}"  # 14 165-174 10 Alphanumeric Originating Direct Clearer's User's ID
            f"{(payment.payment_reference or ''):19.19}"  # 15 175-193 19 Alphanumeric Originator's Cross Reference No.
            f"{originator_account_fin_inst_nr:0>9}"  # 16 194-202 9 Numeric Institutional ID Number for Returns (RBC says to zero-fill)
            f"{originator_account:12.12}"  # 17 203-214 12 Alphanumeric Account No. for Returns (RBC says to zero-fill)
            f"{' ':15}"  # 18 215-229 15 Alphanumeric Originator's Sundry Information (optional)
            f"{' ':22}"  # 19 230-251 22 Alphanumeric Filler
            f"{' ':2}"  # 20 252-253 2 Alphanumeric Originator-Direct Clearer Settlement code (RBC says to zero-fill)
            f"{0:011d}"  # 21 254-264 11 Numeric Invalid Data Element I.D.
            f"{' ':1200}"  # padding for segments 2-6, in practice only one payment is provided per record
        )

    def _l10n_ca_cpa005_generate_footer(self, file_creation_nr, logical_record_count):
        journal = self.journal_id
        payments = self.payment_ids

        # Inbound batches produce "D" debit records, outbound batches produce "C" credit records.
        # In theory you could have both C and D records in the same CPA file, but for now
        # Odoo batch payments, where it's generated, can only contain inbound OR outbound, not a mix of both.
        is_inbound = self.batch_type == 'inbound'
        total_cents = self._l10n_ca_cpa005_get_total_cents(payments)
        debit_value, debit_count = (total_cents, len(payments)) if is_inbound else (0, 0)
        credit_value, credit_count = (0, 0) if is_inbound else (total_cents, len(payments))

        return remove_accents(
            "Z"  # 01 1 1 "Z" Logical Record Type ID
            f"{logical_record_count:09d}"  # 02 2-10 9 Numeric Logical Record Count
            f"{journal.l10n_ca_cpa005_originator_id:10.10}{file_creation_nr:0>4.4}"  # 03 11-24 14 Alphanumeric Origination Control Data (originator ID + Numeric File Creation No.)
            f"{debit_value:014d}"  # 04 25-38 14 Numeric Total Value of Debit Transactions "D" and "J"
            f"{debit_count:08d}"  # 05 39-46 8 Numeric Total Number of Debit Transactions "D" and "J"
            f"{credit_value:014d}"  # 06 47-60 14 Numeric Total Value of Credit Transactions "C" and "I"
            f"{credit_count:08d}"  # 07 61-68 8 Numeric Total Number of Credit Transactions "C" and "I"
            f"{0:014d}"  # 08 69-82 14 Numeric Total Value of Error Corrections "E"
            f"{0:08d}"  # 09 83-90 8 Numeric Total Number of Error Corrections "E"
            f"{0:014d}"  # 10 91-104 14 Numeric Total Value of Error Corrections "F"
            f"{0:08d}"  # 11 105-112 8 Numeric Total Number of Error Corrections "F"
            f"{' ':1352}"  # 12 113-1464 1352 Alphanumeric Filler
        )

    def _generate_cpa005_file(self):
        records = []

        self._l10n_ca_cpa005_pre_validate()
        currency = self._l10n_ca_cpa005_get_currency()

        file_creation_nr = self.l10n_ca_cpa005_file_creation_number
        if not file_creation_nr:
            file_creation_nr = self.journal_id._l10n_ca_cpa005_next_file_creation_nr(self.batch_type)
            self.l10n_ca_cpa005_file_creation_number = file_creation_nr

        records.append(self._l10n_ca_cpa005_generate_header(currency, file_creation_nr))
        for payment in self.payment_ids.sorted():
            records.append(self._l10n_ca_cpa005_transaction_record(file_creation_nr, payment, len(records) + 1))
        records.append(self._l10n_ca_cpa005_generate_footer(file_creation_nr, len(records) + 1))

        return "\r\n".join(records)

    def _get_methods_generating_files(self):
        res = super()._get_methods_generating_files()
        res.append("cpa005")
        return res

    def _generate_export_file(self):
        if self.payment_method_code != 'cpa005':
            return super()._generate_export_file()

        data = self._generate_cpa005_file()
        date = fields.Datetime.today().strftime('%Y-%m-%d')  # CA date format
        prefix = 'CPA005-PAD' if self.batch_type == 'inbound' else 'CPA005'
        return {
            'file': BinaryBytes(data.encode()),
            'filename': '%s-%s-%s.txt' % (prefix, self.journal_id.code, date),
        }
