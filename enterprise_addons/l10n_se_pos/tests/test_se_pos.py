from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nSePos(TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPointOfSaleHttpCommon.setup_country('se')
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data['company']
        company.vat = 'SE123456789701'
        company.partner_id.additional_identifiers = {'SE_EN': '555555-5555'}

    def test_l10n_se_pos_01(self):
        """ Test PoS works seamless with Swedish Fiscal Data Module. """
        # Create IoT Box
        iot_box_id = self.env['iot.box'].sudo().create({
            'name': 'iotbox-test',
            'identifier': '01:01:01:01:01:01',
            'ip': '1.1.1.1',
        })
        # Create IoT device
        fdm_device_id = self.env['iot.device'].sudo().create({
            'iot_id': iot_box_id.id,
            'name': 'Swedish Fiscal Data Module',
            'identifier': 'test_se_fiscal_data_module',
            'type': 'fiscal_data_module',
            'connection': 'direct',
        })
        self.tax_se = self.env['account.tax'].search([], limit=1)
        self.magnetic_board.write({'taxes_id': [(6, 0, self.tax_se.ids)]})
        self.main_pos_config.write({
            'use_iot_box': True,
            'iot_fdm_se_id': fdm_device_id.id,
        })

        self.main_pos_config.open_ui()
        self.start_pos_tour('test_l10n_se_pos_01', login="accountman")
        last_order = self.env['pos.order'].search([], limit=1, order='id desc')
        self.assertEqual(last_order.state, 'paid', "The last order should be paid successfully.")
