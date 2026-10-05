# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@odoo.tests.tagged('post_install', '-at_install')
class TestPosPreparationDisplayLoading(TestPoSCommon):
    # Tests for the preparation display data loading architecture.

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.display = cls.env['pos.prep.display'].create({
            'name': 'Test Display',
            'pos_config_ids': [Command.link(cls.config.id)],
        })

    def _create_display(self, name, config_ids=None):
        """Helper to create a pos.prep.display linked to the given configs."""
        if config_ids is None:
            config_ids = []
        return self.env['pos.prep.display'].create({
            'name': name,
            'pos_config_ids': [Command.link(cid) for cid in config_ids],
        })

    def test_load_preparation_data_response_structure(self):
        """load_preparation_data() must return fields, relations and records for every model."""
        data = self.display.load_preparation_data()

        self.assertTrue(data, "load_preparation_data() should return a non-empty dict")
        for model_name, model_data in data.items():
            self.assertIn('fields', model_data,
                f"[{model_name}] Missing 'fields' key")
            self.assertIn('relations', model_data,
                f"[{model_name}] Missing 'relations' key")
            self.assertIn('records', model_data,
                f"[{model_name}] Missing 'records' key")
            self.assertIsInstance(model_data['records'], list,
                f"[{model_name}] 'records' should be a list")

    def test_load_preparation_data_contains_display_record(self):
        """pos.prep.display must be present in the response with at least the loaded record."""
        data = self.display.load_preparation_data()

        self.assertIn('pos.prep.display', data)
        display_ids = [r['id'] for r in data['pos.prep.display']['records']]
        self.assertIn(self.display.id, display_ids,
            "The loaded display should appear in its own response")

    def test_load_preparation_data_contains_expected_models(self):
        """All models declared in _load_preparation_data_models() must be present."""
        expected_models = self.display._load_preparation_data_models()
        data = self.display.load_preparation_data()

        for model in expected_models:
            self.assertIn(model, data,
                f"Expected model '{model}' missing from load_preparation_data() response")

    # -------------------------------------------------------------------------
    # _load_pos_data_domain: resolves pos.config from data dict
    # -------------------------------------------------------------------------

    def test_load_pos_data_domain_filters_by_config(self):
        """_load_pos_data_domain on pos.prep.display must filter by the pos.config
        found in the data dict, not accept a config argument directly."""
        config_a = self.env['pos.config'].create({'name': 'Config A'})
        config_b = self.env['pos.config'].create({'name': 'Config B'})

        display_a = self._create_display('Display A', config_ids=[config_a.id])
        display_b = self._create_display('Display B', config_ids=[config_b.id])
        display_any = self._create_display('Display Any')  # linked to no config → visible everywhere

        config_a.open_ui()
        config_b.open_ui()

        data_a = config_a.current_session_id.load_data({'only_records': True})
        data_b = config_b.current_session_id.load_data({'only_records': True})

        ids_a = {r['id'] for r in data_a.get('pos.prep.display', [])}
        ids_b = {r['id'] for r in data_b.get('pos.prep.display', [])}

        self.assertIn(display_a.id, ids_a,
            "display_a should be visible for config_a")
        self.assertNotIn(display_b.id, ids_a,
            "display_b should NOT be visible for config_a")
        self.assertIn(display_any.id, ids_a,
            "display_any (no config restriction) should be visible for config_a")

        self.assertIn(display_b.id, ids_b,
            "display_b should be visible for config_b")
        self.assertNotIn(display_a.id, ids_b,
            "display_a should NOT be visible for config_b")
        self.assertIn(display_any.id, ids_b,
            "display_any (no config restriction) should be visible for config_b")

    # -------------------------------------------------------------------------
    # _load_metadata: only the requested display is loaded
    # -------------------------------------------------------------------------

    def test_load_preparation_data_only_own_display(self):
        """load_preparation_data() on a specific display should only load that display's record."""
        display1 = self._create_display('Display One')
        display2 = self._create_display('Display Two')

        data = display1.load_preparation_data()
        display_ids = [r['id'] for r in data['pos.prep.display']['records']]

        self.assertIn(display1.id, display_ids,
            "display1 should be present in its own load_preparation_data()")
        self.assertNotIn(display2.id, display_ids,
            "display2 should NOT appear in display1's load_preparation_data()")

    # -------------------------------------------------------------------------
    # Fields list returned
    # -------------------------------------------------------------------------

    def test_load_preparation_data_fields_list_for_display(self):
        """The 'fields' list for pos.prep.display must contain the declared fields."""
        display = self._create_display('Display Fields Test')
        data = display.load_preparation_data()

        pdis_fields = data['pos.prep.display']['fields']
        expected_fields = display._load_pos_preparation_data_fields()
        for field in expected_fields:
            self.assertIn(field, pdis_fields,
                f"Expected field '{field}' missing from pos.prep.display fields list")
