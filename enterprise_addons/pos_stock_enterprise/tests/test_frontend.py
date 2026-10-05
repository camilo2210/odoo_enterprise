from odoo.addons.pos_stock.tests.test_frontend import TestPosStockHttpCommon
from odoo.addons.pos_enterprise.tests.test_frontend import TestPreparationDisplayHttpCommon
from odoo.addons.point_of_sale.tests.common_setup_methods import setup_product_combo_items


class TestUi(TestPreparationDisplayHttpCommon, TestPosStockHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_03_preparation_display_front_end(self):
        setup_product_combo_items(self)
        self.monitor_stand.tracking = 'serial'
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('MakePosOrderWithCombo')

        self.start_pdis_tour('PreparationDisplayFrontEndTour')
        order = self.main_pos_config.current_session_id.order_ids[0]
        preparation_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)
        prep_line = preparation_order.prep_line_ids[0]
        self.assertEqual(prep_line.pos_order_line_id.pack_lot_ids[0].lot_name, "147259")
