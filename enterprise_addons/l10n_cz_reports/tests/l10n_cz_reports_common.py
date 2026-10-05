from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


class CzechReportsCommon(AccountSalesReportCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('cz')
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_eu_1 = cls.env['res.partner'].create({
            'name': 'Partner EU 1',
            'country_id': cls.env.ref('base.fr').id,
            'vat': 'FR23334175221',
        })
        cls.partner_eu_2 = cls.env['res.partner'].create({
            'name': 'Partner EU 2',
            'country_id': cls.env.ref('base.de').id,
            'vat': 'DE123456788',
        })
        cls.partner_eu_3 = cls.env['res.partner'].create({
            'name': 'Partner EU 3',
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0477472701',
        })
        cls.partner_eu_4 = cls.env['res.partner'].create({
            'name': 'Partner EU 4',
            'country_id': cls.env.ref('base.be').id,
            'vat': '0477472701',
        })

        cls.partner_cz_1 = cls.env['res.partner'].create({
            'name': 'Partner CZ 1',
            'country_id': cls.env.ref('base.cz').id,
            'vat': 'CZ00000001',
        })

        cls.partner_cz_2 = cls.env['res.partner'].create({
            'name': 'Partner CZ 2',
            'country_id': cls.env.ref('base.cz').id,
            'vat': 'CZ11111119',
        })

        cls.partner_non_eu = cls.env['res.partner'].create({
            'name': 'Partner Non-EU',
            'country_id': cls.env.ref('base.br').id,
        })

        cls.company = cls.env.company
        cls.company.write({
            'country_id': cls.env.ref('base.cz').id,
            'city': 'PRAGUE 1',
            'street': 'Pařížská Street 25',
            'l10n_cz_economic_activity_code': '10000',
        })
        cls.company_id = cls.company.id
        # Define a contact belonging to the company, so it passes checks in `validate_czech_company_fields()`
        cls.env['res.partner'].create({
            'name': 'company partner',
            'parent_id': cls.company.partner_id.id,
        })

        # Sale Taxes
        cls.l10n_cz_21_domestic_supplies = cls.env.ref(f'account.{cls.company_id}_l10n_cz_21_domestic_supplies')
        cls.l10n_cz_12_domestic_supplies = cls.env.ref(f'account.{cls.company_id}_l10n_cz_12_domestic_supplies')
        cls.l10n_cz_tax_reverse_charge_mode = cls.env.ref(f'account.{cls.company_id}_l10n_cz_tax_reverse_charge_mode')
        cls.l10n_cz_investment_gold = cls.env.ref(f'account.{cls.company_id}_l10n_cz_investment_gold')
        # Purchase Taxes
        cls.l10n_cz_21_receipt_domestic_supplies = cls.env.ref(f'account.{cls.company_id}_l10n_cz_21_receipt_domestic_supplies')
        cls.l10n_cz_12_receipt_domestic_supplies = cls.env.ref(f'account.{cls.company_id}_l10n_cz_12_receipt_domestic_supplies')
        cls.l10n_cz_21_tax_reverse_charge_scheme = cls.env.ref(f'account.{cls.company_id}_l10n_cz_21_tax_reverse_charge_scheme')
        cls.l10n_cz_12_tax_reverse_charge_scheme = cls.env.ref(f'account.{cls.company_id}_l10n_cz_12_tax_reverse_charge_scheme')
        cls.l10n_cz_21_acquisition_goods_eu = cls.env.ref(f'account.{cls.company_id}_l10n_cz_21_acquisition_goods_eu')
        cls.l10n_cz_12_purchase_goods_eu = cls.env.ref(f'account.{cls.company_id}_l10n_cz_12_purchase_goods_eu')
        cls.l10n_cz_21_receipt_service_person_eu = cls.env.ref(f'account.{cls.company_id}_l10n_cz_21_receipt_service_person_eu')
        cls.l10n_cz_12_receipt_service_person_eu = cls.env.ref(f'account.{cls.company_id}_l10n_cz_12_receipt_service_person_eu')
        cls.l10n_cz_acquisition_transport = cls.env.ref(f'account.{cls.company_id}_l10n_cz_acquisition_transport')
        cls.l10n_cz_21_receipt_service_person_non_eu = cls.env.ref(f'account.{cls.company_id}_l10n_cz_21_receipt_service_person_non_eu')
        cls.l10n_cz_12_receipt_service_person_non_eu = cls.env.ref(f'account.{cls.company_id}_l10n_cz_12_receipt_service_person_non_eu')

        cls.company.update({
            'country_id': cls.env.ref('base.cz').id,
            'vat': 'CZ12345679',
            'l10n_cz_tax_office_id': cls.env.ref('l10n_cz.tax_office_1'),
            'email': 'info@company.czexample.com',
        })
