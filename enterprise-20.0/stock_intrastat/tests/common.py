from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


class TestStockIntrastatCommon(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(self):
        super().setUpClass()

        self.company_data['company'].country_id = self.env.ref('base.be')
        self.company_data['company'].vat = 'BE0897223670'
        self.company_data['company'].intrastat_region_id = self.env['account.intrastat.code'].sudo().create({
            'code': 1000,
            'name': 'Region1',
            'type': 'region',
            'country_id': self.env.ref('base.be').id,
        })

        self.partner_a.country_id = self.env.ref('base.fr')
        self.partner_a.vat = 'FR23334175221'

        self.warehouse = self.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'code': 'TW',
            'intrastat_region_id': self.env['account.intrastat.code'].sudo().create({
                'code': 2000,
                'name': 'Region2',
                'type': 'region',
                'country_id': self.env.ref('base.be').id,
            }).id,
        })

        self.product = self.env['product.product'].create({
            'name': "Test Product",
            'list_price': 100.0,
            'type': 'consu',
            'uom_id': self.uom_unit.id,
            'intrastat_code_id': self.env.ref('account_intrastat.commodity_code_2018_88023000').id,
            'intrastat_supplementary_unit_amount': 2,
            'weight': 100,
            'intrastat_origin_country_id': self.env.ref('base.be').id,
        })
