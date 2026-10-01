from odoo.addons.account_avatax.tests.common import TestAccountAvataxCommon
from odoo.tests.common import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUsReportsAvatax(TestAccountAvataxCommon):
    _test_user_groups = ('account.group_account_invoice',)

    def _post_invoice(self, details):
        """ Post a 100.0 invoice whose Avatax response holds the given jurisdiction details. """
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'fiscal_position_id': self.fp_avatax.id,
            'invoice_date': '2021-01-01',
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product_user.id,
                    'tax_ids': None,
                    'price_unit': 100.00,
                }),
            ],
        })
        lines = [{
            'details': details,
            'lineAmount': 100.0,
            'lineNumber': 'account.move.line,' + str(invoice.invoice_line_ids.id),
            'tax': sum(detail['tax'] for detail in details),
        }]
        with self._capture_request(return_value={'lines': lines, 'summary': []}):
            invoice.action_post()
        return invoice

    def _get_tax(self, name):
        return self.env['account.tax'].with_context(active_test=False).search([
            ('name', '=', name),
            ('company_id', '=', self.env.company.id),
        ])

    def _county_detail(self, **overrides):
        return {
            'jurisCode': '075',
            'jurisdictionType': 'County',
            'jurisName': 'SAN FRANCISCO',
            'region': 'CA',
            'rate': 0.06,
            'taxName': 'CA COUNTY TAX',
            'nonTaxableAmount': 0.0,
            'taxableAmount': 0.0,
            'tax': 0.0,
            **overrides,
        }

    def test_nontaxable_creates_missing_parent_tax(self):
        """ Test that a standard parent tax gets created to link the nontaxable tax. """
        self._post_invoice([self._county_detail(nonTaxableAmount=100.0)])

        variant = self._get_tax('CA COUNTY 6% (Non-Taxable)')
        parent = self._get_tax('CA COUNTY 6%')
        self.assertRecordValues(variant, [{
            'amount': 0.0,
            'l10n_us_nontaxable_parent_tax_id': parent.id,
            'l10n_us_exempt_parent_tax_id': False,
        }])
        self.assertRecordValues(parent, [{
            'amount': 6.0,
            'amount_type': 'percent',
            'type_tax_use': variant.type_tax_use,
            'tax_group_id': variant.tax_group_id.id,
            'l10n_us_jurisdiction_type': 'county',
            'l10n_us_state_id': self.env.ref('base.state_us_5').id,
        }])

    def test_city_jurisdiction_reports_its_state(self):
        """ Test that a city jurisdiction is reported under its state, without a city record. """
        self._post_invoice([self._county_detail(
            jurisdictionType='City',
            jurisName='UNINCORPORATED SAN FRANCISCO',
            taxName='CA CITY TAX',
            taxableAmount=100.0,
            tax=6.0,
        )])

        self.assertRecordValues(self._get_tax('CA CITY 6%'), [{
            'l10n_us_jurisdiction_type': 'city',
            'l10n_us_state_id': self.env.ref('base.state_us_5').id,
            'l10n_us_city_id': False,
        }])

    def test_exempt_links_to_existing_parent_tax(self):
        """ Tests that an exempt variant links to an existing tax rather than creating a new one. """
        self._post_invoice([self._county_detail(taxableAmount=100.0, tax=6.0)])
        parent = self._get_tax('CA COUNTY 6%')
        self.assertTrue(parent, "the taxable jurisdiction rate should have been created")

        self._post_invoice([self._county_detail(exemptAmount=100.0)])

        self.assertEqual(self._get_tax('CA COUNTY 6%'), parent, "no second taxable rate should be created")
        variant = self._get_tax('CA COUNTY 6% (Exempt)')
        self.assertRecordValues(variant, [{
            'amount': 0.0,
            'l10n_us_exempt_parent_tax_id': parent.id,
            'l10n_us_nontaxable_parent_tax_id': False,
        }])
