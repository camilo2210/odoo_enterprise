from odoo.addons.l10n_es_reports.tests.common import TestEsAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nEsAccountReturn(TestEsAccountReportsCommon):
    """
    Check the specificities of the Spanish's implementation of account.return
    """
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod111_return_type = cls.env.ref('l10n_es_reports.es_mod111_tax_return_type')
        cls.mod115_return_type = cls.env.ref('l10n_es_reports.es_mod115_tax_return_type')
        cls.mod349_return_type = cls.env.ref('l10n_es_reports.es_mod349_tax_return_type')

        cls.mod_numbers = (111, 115, 303, 347, 349, 390)
        cls.tax_returns_mod_numbers = (111, 115, 303)

        cls.all_return_types = cls.env['account.return.type']
        for mod in cls.mod_numbers:
            cls.all_return_types |= cls.env.ref(f'l10n_es_reports.es_mod{mod}_tax_return_type')

    def test_compute_is_tax_return(self):
        """is_tax_return should be correctly computed for Spanish reports."""
        for return_type in self.all_return_types:
            with self.subTest(f'{return_type.name} - return type'):
                account_return = self.env['account.return'].create({
                    'name': f'Test {return_type.name}',
                    'type_id': return_type.id,
                    'company_id': self.company.id,
                    'date_from': '2023-01-01',
                    'date_to': '2023-01-31',
                })
                if account_return._l10n_es_get_report_modelo_number() in self.tax_returns_mod_numbers:
                    self.assertTrue(return_type.is_tax_return_type)
                else:
                    self.assertFalse(return_type.is_tax_return_type)

    def test_get_vat_closing_entry_additional_domain(self):
        """Additional domain for tax closing entries for mod 111 and 115"""
        with self.subTest('Mod111 -> closing entry\'s domain'):
            account_return = self.env['account.return'].create({
                'name': 'Test mod111 domain',
                'type_id': self.mod111_return_type.id,
                'company_id': self.company.id,
                'date_from': '2023-01-01',
                'date_to': '2023-01-31',
            })
            domain = account_return._get_vat_closing_entry_additional_domain()
            mod111_tags = self.env.ref('l10n_es.mod_111').line_ids.expression_ids._get_matching_tags()
            domain_111 = ('tax_tag_ids', 'in', mod111_tags.ids)
            self.assertIn(domain_111, domain)

        with self.subTest('Mod115 -> closing entry\'s domain'):
            account_return = self.env['account.return'].create({
                'name': 'Test mod115 domain',
                'type_id': self.mod115_return_type.id,
                'company_id': self.company.id,
                'date_from': '2023-01-01',
                'date_to': '2023-01-31',
            })
            domain = account_return._get_vat_closing_entry_additional_domain()
            mod115_tags = self.env.ref('l10n_es.mod_115').line_ids.expression_ids._get_matching_tags()
            domain_115 = ('tax_tag_ids', 'in', mod115_tags.ids)
            self.assertIn(domain_115, domain)

    def test_open_tax_return_in_es_company(self):
        """Test that we can open a tax return in a company with country set to Spain."""
        account_return = self.env['account.return'].create({
            'name': 'Test mod349 return',
            'type_id': self.mod349_return_type.id,
            'company_id': self.company.id,
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
        })
        account_return.refresh_checks()
        self.assertTrue(account_return.check_ids, "The tax return should have checks generated")
