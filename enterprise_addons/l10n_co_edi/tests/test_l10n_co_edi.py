from .common import TestCoEdiCommon
from odoo.tests import tagged

@tagged('post_install_l10n', 'post_install', '-at_install')
class TestColombianInvoice(TestCoEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_setup_tax_type(self):
        for xml_id, expected_type in [
            ("account.l10n_co_tax_4", "l10n_co_edi.tax_type_0"),
            ("account.l10n_co_tax_8", "l10n_co_edi.tax_type_0"),
            ("account.l10n_co_tax_9", "l10n_co_edi.tax_type_0"),
            ("account.l10n_co_tax_10", "l10n_co_edi.tax_type_0"),
            ("account.l10n_co_tax_11", "l10n_co_edi.tax_type_0"),
            ("account.l10n_co_tax_53", "l10n_co_edi.tax_type_5"),
            ("account.l10n_co_tax_54", "l10n_co_edi.tax_type_5"),
            ("account.l10n_co_tax_55", "l10n_co_edi.tax_type_4"),
            ("account.l10n_co_tax_56", "l10n_co_edi.tax_type_4"),
            ("account.l10n_co_tax_57", "l10n_co_edi.tax_type_6"),
            ("account.l10n_co_tax_58", "l10n_co_edi.tax_type_6"),
            ("account.l10n_co_tax_covered_goods", "l10n_co_edi.tax_type_0")
        ]:
            tax = self.env.ref(xml_id, raise_if_not_found=False)
            if tax:
                self.assertEqual(tax.l10n_co_edi_type, expected_type)

    def test_debit_note_creation_wizard(self):
        """ Test debit note is create succesfully """
        taxes = self.company_data['default_tax_sale']
        taxes += taxes[0].copy({
            'name': 'retention_tax',
            'l10n_co_edi_type': self.env.ref('l10n_co_edi.tax_type_9').id
        })
        invoice = self._create_invoice(
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product_a,
                    quantity=150,
                    price_unit=250,
                    discount=10,
                    name='Line 1',
                    tax_ids=taxes,
                ),
            ],
            post=True,
        )

        wizard = self.env['account.debit.note'].with_context(active_model="account.move", active_ids=invoice.ids).create({
            'l10n_co_edi_description_code_debit': '1',
            'copy_lines': True,
        })
        wizard.create_debit()

        debit_note = self.env['account.move'].search([
            ('debit_origin_id', '=', invoice.id),
        ])
        self.assertRecordValues(debit_note, [{'amount_total': 46575.0}])

    def test_is_company(self):
        self.assertEqual(self.env.ref('l10n_co_edi.consumidor_final_customer').is_company, False)
        co = self.env.ref('base.co')

        nit_partner = self.env['res.partner'].create({
            'name': 'CO Company NIT',
            'country_id': co.id,
            'vat': '900108281',
        })
        self.assertTrue(nit_partner.is_company)

        child = self.env['res.partner'].create({
            'name': 'CO Child Contact',
            'parent_id': nit_partner.id,
        })
        self.assertFalse(child.is_company)
        self.assertEqual(child.complete_name, f'{nit_partner.name}, {child.name}')
        self.assertIn(
            child,
            self.env['res.partner'].search([('display_name', 'ilike', nit_partner.name)]),
        )

        # a partner responsible for 'R-99-PN' is a natural person, whatever its identification
        nit_partner.l10n_co_edi_obligation_type_ids = self.env.ref('l10n_co_edi.obligation_type_5')
        self.assertFalse(nit_partner.is_company)

        for co_person_identifier in ('CO_CC', 'CO_CE', 'CO_TI'):
            person = self.env['res.partner'].create({
                'name': f'CO Person {co_person_identifier}',
                'country_id': co.id,
                'additional_identifiers': {co_person_identifier: '1234567'},
            })
            self.assertFalse(person.is_company)
            person.write({'additional_identifiers': False, 'vat': '900108281'})
            self.assertTrue(person.is_company)
