from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestFleetVehicle(TransactionCase):

    def test_fleet_vehicle_model_atn_non_belgian_company_no_error(self):
        fr_company = self.env['res.company'].create({
            'name': 'French Test Company',
            'country_id': self.env.ref('base.fr').id,
        })

        brand = self.env['fleet.vehicle.model.brand'].sudo().create({'name': 'FR Brand'})
        fr_model = self.env['fleet.vehicle.model'].sudo().with_company(fr_company).create({
            'name': 'FR Model',
            'brand_id': brand.id,
            'default_car_value': 30000.0,
            'default_fuel_type': 'diesel',
            'default_co2': 90.0,
        })

        # Trigger computation and assert no exception was raised and default_atn evaluates to 0.0
        self.assertEqual(fr_model.current_country_code, 'FR')
        self.assertEqual(fr_model.default_atn, 0.0)
