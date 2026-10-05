from odoo.tests.common import tagged
from .common import TestAccountAvataxCommon


@tagged("-at_install", "post_install")
class TestAvataxParameters(TestAccountAvataxCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.config = cls.env['res.config.settings'].create({})

        cls.mock_uom_response = {
            'value': [
                {'code': 'Inch', 'shortDesc': 'Inches (in, ")', 'measurementTypeCode': 'Length'},
                {'code': 'Centimeter', 'shortDesc': 'Centimeter (cm)', 'measurementTypeCode': 'Length'},
                {'code': 'Kilogram', 'shortDesc': 'Kilogram (kg)', 'measurementTypeCode': 'Mass'},
            ],
        }
        cls.mock_params_response = {
            'value': [
                {
                    'name': 'ScreenSize',
                    'label': 'Screen Size',
                    'helpText': 'The diagonal length of a rectangular screen.',
                    'attributeType': 'Product',
                    'dataType': 'NumericMeasured',
                    'measurementType': 'Length',
                },
                {
                    'name': 'HasEmbeddedBattery',
                    'label': 'Has Embedded Battery',
                    'helpText': 'Whether the product has an embedded battery.',
                    'attributeType': 'Product',
                    'dataType': 'Boolean',
                },
                {
                    'name': 'BeverageContainerMaterial',
                    'label': 'Beverage Container Material',
                    'attributeType': 'Product',
                    'dataType': 'Enumeration',
                    'values': ['Aluminum', 'Glass', 'Plastic'],
                },
                {
                    'name': 'EstablishmentType',
                    'label': 'Establishment Type',
                    'attributeType': 'Company',
                    'dataType': 'Enumeration',
                    'values': ['Hotel', 'Motel'],
                },
            ],
        }
        cls.mock_exemption_response = {'value': []}
        return res

    def _mock_sync(self):
        responses = {
            'list_entity_use_codes': self.mock_exemption_response,
            'list_unit_of_measurements': self.mock_uom_response,
            'list_parameters': self.mock_params_response,
        }
        with self._capture_request(return_func=lambda iap_endpoint, *a, **kw: responses.get(iap_endpoint, {})):
            self.config.avatax_sync_company_params()

    def test_sync_creates_records(self):
        self._mock_sync()

        uoms = self.env['avatax.uom'].search([])
        self.assertEqual(len(uoms), 3)
        self.assertEqual(set(uoms.mapped('code')), {'Inch', 'Centimeter', 'Kilogram'})
        inch = uoms.filtered(lambda u: u.code == 'Inch')
        self.assertEqual(inch.measurement_type, 'Length')
        self.assertEqual(inch.name, 'Inches (in, ")')

        params = self.env['avatax.parameter'].search([])
        self.assertEqual(len(params), 3, "Only Product-type parameters should be synced")
        self.assertFalse(params.filtered(lambda p: p.technical_name == 'EstablishmentType'))

        screen_size = params.filtered(lambda p: p.technical_name == 'ScreenSize')
        self.assertEqual(screen_size.data_type, 'NumericMeasured')
        self.assertEqual(screen_size.measurement_type, 'Length')

        container = params.filtered(lambda p: p.technical_name == 'BeverageContainerMaterial')
        self.assertEqual(set(container.selection_ids.mapped('name')), {'Aluminum', 'Glass', 'Plastic'})

    def test_sync_no_duplicates(self):
        self._mock_sync()
        self._mock_sync()

        self.assertEqual(self.env['avatax.uom'].search_count([]), 3)
        self.assertEqual(self.env['avatax.parameter'].search_count([]), 3)
        container = self.env['avatax.parameter'].search([('technical_name', '=', 'BeverageContainerMaterial')])
        self.assertEqual(len(container.selection_ids), 3, "Selections should not be duplicated")

    def test_sync_updates_existing(self):
        self._mock_sync()

        self.mock_uom_response['value'][0]['measurementTypeCode'] = 'Area'
        self.mock_params_response['value'][0]['label'] = 'Display Size'
        self.mock_params_response['value'][0]['helpText'] = 'Updated description'
        self.mock_params_response['value'][2]['values'].append('Steel')
        self.mock_params_response['value'].append({
            'name': 'Brand',
            'label': 'Brand',
            'attributeType': 'Product',
            'dataType': 'String',
        })
        self._mock_sync()

        inch = self.env['avatax.uom'].search([('code', '=', 'Inch')])
        self.assertEqual(inch.measurement_type, 'Area', "UOM measurement_type should be updated")

        screen_size = self.env['avatax.parameter'].search([('technical_name', '=', 'ScreenSize')])
        self.assertEqual(screen_size.name, 'Display Size', "Parameter name should be updated")
        self.assertEqual(screen_size.description, 'Updated description')

        container = self.env['avatax.parameter'].search([('technical_name', '=', 'BeverageContainerMaterial')])
        self.assertEqual(len(container.selection_ids), 4, "New selection should be added")
        self.assertIn('Steel', container.selection_ids.mapped('name'))

        self.assertEqual(self.env['avatax.parameter'].search_count([]), 4, "New param should be created")
        brand = self.env['avatax.parameter'].search([('technical_name', '=', 'Brand')])
        self.assertEqual(brand.data_type, 'String')

    def test_parameters_sent_on_line(self):
        screen_size = self.env['avatax.parameter'].create({
            'technical_name': 'ScreenSize',
            'name': 'Screen Size',
            'scope': 'Product',
            'data_type': 'NumericMeasured',
            'measurement_type': 'Length',
            'company_id': self.env.company.id,
        })
        has_battery = self.env['avatax.parameter'].create({
            'technical_name': 'HasEmbeddedBattery',
            'name': 'Has Embedded Battery',
            'scope': 'Product',
            'data_type': 'Boolean',
            'company_id': self.env.company.id,
        })
        inch = self.env['avatax.uom'].create({
            'name': 'Inches (in, ")',
            'code': 'Inch',
            'measurement_type': 'Length',
            'company_id': self.env.company.id,
        })
        self.product.write({
            'avatax_parameter_value_ids': [
                (0, 0, {
                    'parameter_id': screen_size.id,
                    'value_float': 14.0,
                    'avatax_uom_id': inch.id,
                }),
                (0, 0, {
                    'parameter_id': has_battery.id,
                    'value_boolean': True,
                }),
            ],
        })

        invoice = self._create_invoice_avatax(post=False)
        line_data = invoice._get_line_data_for_external_taxes()
        line_payload = self.env['account.external.tax.mixin']._prepare_avatax_document_line_service_call(
            line_data[0], False,
        )

        self.assertIn('parameters', line_payload)
        params = {p['name']: p for p in line_payload['parameters']}
        self.assertEqual(params['ScreenSize']['value'], '14.000000')
        self.assertEqual(params['ScreenSize']['unit'], 'Inch')
        self.assertEqual(params['HasEmbeddedBattery']['value'], 'true')
        self.assertNotIn('unit', params['HasEmbeddedBattery'])

    def test_no_parameters_on_line(self):
        invoice = self._create_invoice_avatax(post=False)
        line_data = invoice._get_line_data_for_external_taxes()
        line_payload = self.env['account.external.tax.mixin']._prepare_avatax_document_line_service_call(
            line_data[0], False,
        )
        self.assertNotIn('parameters', line_payload)

    def test_parameter_value_computed_field(self):
        param_bool = self.env['avatax.parameter'].create({
            'technical_name': 'TestBool',
            'name': 'Test',
            'scope': 'Product',
            'data_type': 'Boolean',
            'company_id': self.env.company.id,
        })
        param_enum = self.env['avatax.parameter'].create({
            'technical_name': 'TestEnum',
            'name': 'Test',
            'scope': 'Product',
            'data_type': 'Enumeration',
            'company_id': self.env.company.id,
        })
        selection = self.env['avatax.parameter.selection'].create({
            'parameter_id': param_enum.id,
            'name': 'Aluminum',
        })

        val_bool = self.env['avatax.parameter.value'].create({
            'parameter_id': param_bool.id,
            'value_boolean': True,
            'product_id': self.product.id,
        })
        self.assertEqual(val_bool.value, 'true')

        val_enum = self.env['avatax.parameter.value'].create({
            'parameter_id': param_enum.id,
            'value_selection_id': selection.id,
            'product_id': self.product.id,
        })
        self.assertEqual(val_enum.value, 'Aluminum')
