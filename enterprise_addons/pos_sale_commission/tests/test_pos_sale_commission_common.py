# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.sale_commission.tests.test_sale_commission_common import TestSaleCommissionCommon
from odoo.addons.point_of_sale.tests.common import CommonPosTest


class TestPOSSaleCommissionCommon(CommonPosTest, TestSaleCommissionCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.main_pos_config = cls.env['pos.config'].create({
            'name': 'Shop',
            'module_pos_restaurant': False,
        })
        cls.main_pos_config.open_ui()
        current_session = cls.main_pos_config.current_session_id
        cls.partner_1 = cls.env['res.partner'].create({'name': 'Test POS Partner'})
        cls.order = cls.env['pos.order'].create({
            'company_id': cls.env.company.id,
            'session_id': current_session.id,
            'partner_id': cls.partner_1.id,
            'pricelist_id': cls.partner_1.property_product_pricelist.id,
            'lines': [(0, 0, {
                'name': "OL/0001",
                'product_id': cls.commission_product_1.id,
                'price_unit': cls.commission_product_1.lst_price,
                'discount': 0.0,
                'qty': 1.0,
                'tax_ids': [],
                'price_subtotal': cls.commission_product_1.lst_price,
                'price_subtotal_incl': cls.commission_product_1.lst_price,
            })],
            'amount_total': cls.commission_product_1.lst_price,
            'amount_tax': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        })
        cls.env.flush_all()
        cls.env.user.group_ids += cls.quick_ref('sales_team.group_sale_salesman')
