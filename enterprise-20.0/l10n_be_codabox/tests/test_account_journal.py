import base64
from unittest.mock import patch

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


_CODA_TEMPLATE = (
    "0000001022372505        0123456789JOHN DOE                  KREDBEBB   00477472701 00000                                       2\n"
    "12001BE68539007547034                  {cur}0000000000100000310123DEMO COMPANY              KBC Business Account               027\n"
    "2100010000ABCDEFG123456789000010000000000025500010223001500000Payment Reference                                    01022302701 0\n"
    "2200010000                                                                                        GEBABEBB                   1 0\n"
    "2300010000BE55173363943144                     ODOO SA                                                                       0 0\n"
    "8027BE68539007547034                  {cur}0000000000125500010223                                                                0\n"
    "9               000005000000000000000000000000025500                                                                           2"
)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCodaboxJournalRouting(AccountTestInvoicingCommon):
    """When several journals share the same IBAN with different currencies,
    a CODA must land on the journal whose currency matches the file currency,
    and the no-currency journal must not act as a wildcard that steals CODAs
    from currency-specific journals.
    """
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.currency_id = cls.env.ref('base.EUR').id
        cls.company.l10n_be_codabox_is_connected = True

        iban = 'BE68539007547034'

        cls.journal_no_currency = cls.env['account.journal'].create({
            'name': 'Bank (no currency)',
            'type': 'bank',
            'code': 'BNKN',
            'bank_account_number': iban,
            'bank_statements_source': 'undefined',
            'sequence': 1,
        })
        cls.journal_eur = cls.env['account.journal'].create({
            'name': 'Bank (EUR)',
            'type': 'bank',
            'code': 'BNKE',
            'currency_id': cls.env.ref('base.EUR').id,
            'bank_account_number': iban,
            'bank_statements_source': 'undefined',
            'sequence': 99,
        })
        cls.journal_usd = cls.env['account.journal'].create({
            'name': 'Bank (USD)',
            'type': 'bank',
            'code': 'BNKU',
            'currency_id': cls.env.ref('base.USD').id,
            'bank_account_number': iban,
            'bank_statements_source': 'undefined',
            'sequence': 99,
        })

    def _fetch(self, entry_journal, currency_code):
        fake_coda = [[base64.b64encode(_CODA_TEMPLATE.format(cur=currency_code).encode('utf-8')).decode(), base64.b64encode(b'%PDF-1.4').decode()]]
        with patch.object(self.env.registry['account.journal'], '_l10n_be_codabox_fetch_transactions_from_iap', return_value=fake_coda):
            entry_journal._l10n_be_codabox_fetch_coda_transactions(self.company)

    def _imported_statement(self):
        statements = self.env['account.bank.statement'].search([('company_id', '=', self.company.id)])
        self.assertEqual(len(statements), 1)
        return statements

    def test_eur_coda_lands_on_explicit_eur_journal(self):
        self._fetch(self.journal_no_currency, 'EUR')
        self.assertEqual(self._imported_statement().journal_id, self.journal_eur)

    def test_coda_falls_back_to_no_currency_journal_when_no_dedicated_journal(self):
        self.journal_eur.sudo().unlink()
        self._fetch(self.journal_no_currency, 'EUR')
        self.assertEqual(self._imported_statement().journal_id, self.journal_no_currency)
