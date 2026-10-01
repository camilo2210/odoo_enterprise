from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ca_payment_cpa005.tests.common import CPA005Common


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCPA005PADMandate(CPA005Common):

    def test_cpa005_pad_mandate_validate_non_iban(self):
        """A CPA005 PAD mandate validates with a non-IBAN Canadian account that has an FI number."""
        mandate = self._create_cpa005_mandate(validate=False)
        mandate.action_validate_mandate()
        self.assertEqual(mandate.state, 'active')

    def test_cpa005_pad_mandate_requires_fi_number(self):
        """Validation fails when the customer bank account has no FI number."""
        bank_no_fi = self._create_ca_bank(partner_id=self.partner_a, account_number='999000111')
        mandate = self._create_cpa005_mandate(partner_bank_id=bank_no_fi, validate=False)
        with self.assertRaisesRegex(UserError, "A CPA 005 PAD mandate requires a customer bank account with a Financial Institution ID Number."):
            mandate.action_validate_mandate()

    def test_cpa005_pad_fi_number_split(self):
        """The FI number splits into institution (3) and transit (5) for the PAD form."""
        self.assertEqual(self.bank_partner_a.l10n_ca_cpa005_institution_number, '555')
        self.assertEqual(self.bank_partner_a.l10n_ca_cpa005_transit_number, '66666')

    def test_cpa005_pad_mandate_pdf_renders(self):
        """Generating the PAD mandate PDF must render the report without error."""
        self.bank_partner_a.bank_name = 'Royal Bank of Canada'
        mandate = self._create_cpa005_mandate()
        wizard = self.env['account.mandate.send.wizard'].create({'mandate_id': mandate.id})
        pdf_data = wizard._prepare_mandate_pdf()
        # In test mode the report renders as HTML; the financial institution name must appear.
        self.assertIn(b"Royal Bank of Canada", pdf_data['raw'])
