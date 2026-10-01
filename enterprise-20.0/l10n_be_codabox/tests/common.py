import base64

from odoo.tools import file_open
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestCodaboxCommon(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        bank_1, bank_2 = cls.env['res.partner.bank'].create([
            {'account_number': 'BE33737018595246', 'partner_id': cls.env.company.partner_id.id},
            {'account_number': 'BE33737018595247', 'partner_id': cls.env.company.partner_id.id},
        ])
        cls.bank_journal_1 = cls.company_data['default_journal_bank']
        cls.bank_journal_1.bank_account_id = bank_1
        cls.bank_journal_2 = cls.bank_journal_1.copy({'bank_account_id': bank_2.id})
        with file_open('l10n_be_coda/test_coda_file/Ontvangen_CODA.2013-01-11-18.59.15.txt', 'rb') as coda_file:
            cls.coda_file_b64 = base64.b64encode(coda_file.read()).decode()
        with file_open('l10n_be_coda/test_coda_file/multi_accounts.COD', 'rb') as coda_file:
            cls.coda_file_multi_accounts_b64 = base64.b64encode(coda_file.read()).decode()
        with file_open('l10n_be_coda/test_coda_file/multi_accounts_extension.COD', 'rb') as coda_file:
            cls.coda_file_multi_accounts_extension_b64 = base64.b64encode(coda_file.read()).decode()
