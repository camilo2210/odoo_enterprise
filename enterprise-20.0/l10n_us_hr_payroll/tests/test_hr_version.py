# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrVersion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.country_us = cls.env.ref('base.us')
        cls.state_ca = cls.env.ref('base.state_us_5')
        cls.city_la = cls.env.ref('l10n_us.city_us_02')

        cls.states = {
            'NY': cls.env['res.country.state'].search([('code', '=', 'NY')], limit=1),
            'CA': cls.env['res.country.state'].search([('code', '=', 'CA')], limit=1),
            'AL': cls.env['res.country.state'].search([('code', '=', 'AL')], limit=1),
            'CO': cls.env['res.country.state'].search([('code', '=', 'CO')], limit=1),
            'VT': cls.env['res.country.state'].search([('code', '=', 'VT')], limit=1),
            'IL': cls.env['res.country.state'].search([('code', '=', 'IL')], limit=1),
            'AZ': cls.env['res.country.state'].search([('code', '=', 'AZ')], limit=1),
            'DC': cls.env['res.country.state'].search([('code', '=', 'DC')], limit=1),
            'NC': cls.env['res.country.state'].search([('code', '=', 'NC')], limit=1),
            'VA': cls.env['res.country.state'].search([('code', '=', 'VA')], limit=1),
            'OR': cls.env['res.country.state'].search([('code', '=', 'OR')], limit=1),
            'ID': cls.env['res.country.state'].search([('code', '=', 'ID')], limit=1),
            'TX': cls.env['res.country.state'].search([('code', '=', 'TX')], limit=1),
        }

        cls.expected_statuses = {
            'NY': 'ny_status_1',
            'CA': 'ca_status_1',
            'AL': 'al_status_1',
            'CO': 'co_status_1',
            'VT': 'vt_status_1',
            'IL': 'il_status_1',
            'AZ': 'az_status_4',
            'DC': 'dc_status_1',
            'NC': 'nc_status_1',
            'VA': 'va_status_1',
            'OR': 'or_status_1',
            'ID': 'id_status_1',
        }

    def test_default_hr_version_creation(self):
        """ Ensure no constraints trigger when creating a default contract template. """
        self.env.company.state_id = self.env.ref("base.state_us_5")
        self.env['hr.version'].create({'name': 'test'})

    def test_supported_states_default_filing_status(self):
        """All supported states get correct default filing status"""
        for state_code, expected_status in self.expected_statuses.items():
            address = self.env['res.partner'].create({
                'name': f'{state_code} Address',
                'state_id': self.states[state_code].id,
            })
            employee = self.env['hr.employee'].create({
                'name': f'Test Employee {state_code}',
                'address_id': address.id,
            })
            self.assertEqual(
                employee.l10n_us_state_filing_status,
                expected_status,
                f"Employee in {state_code} should have filing status {expected_status}"
            )

    def test_unsupported_state_filing_status(self):
        """Unsupported state (TX) gets False filing status"""
        address_tx = self.env['res.partner'].create({
            'name': 'TX Address',
            'state_id': self.states['TX'].id,
        })
        employee_tx = self.env['hr.employee'].create({
            'name': 'Test Employee TX',
            'address_id': address_tx.id,
        })
        self.assertFalse(
            employee_tx.l10n_us_state_filing_status,
            "Employee in unsupported state should have False filing status"
        )

    def test_no_state_filing_status(self):
        """No state gets False filing status"""
        address_no_state = self.env['res.partner'].create({
            'name': 'No State Address',
        })
        employee_no_state = self.env['hr.employee'].create({
            'name': 'Test Employee No State',
            'address_id': address_no_state.id,
        })
        self.assertFalse(
            employee_no_state.l10n_us_state_filing_status,
            "Employee without state should have False filing status"
        )

    def test_state_change_updates_filing_status(self):
        """State change from NY to CA updates filing status"""
        address_ny = self.env['res.partner'].create({
            'name': 'NY Address',
            'state_id': self.states['NY'].id,
        })
        address_ca = self.env['res.partner'].create({
            'name': 'CA Address',
            'state_id': self.states['CA'].id,
        })
        employee_change = self.env['hr.employee'].create({
            'name': 'Test Employee State Change',
            'address_id': address_ny.id,
        })
        self.assertEqual(employee_change.l10n_us_state_filing_status, 'ny_status_1')

        employee_change.address_id = address_ca.id
        self.assertEqual(
            employee_change.l10n_us_state_filing_status,
            'ca_status_1',
            "Filing status should update when state changes from NY to CA"
        )

    def test_state_change_to_unsupported_clears_filing_status(self):
        """State change from supported to unsupported clears filing status"""
        address_ny = self.env['res.partner'].create({
            'name': 'NY Address',
            'state_id': self.states['NY'].id,
        })
        address_tx = self.env['res.partner'].create({
            'name': 'TX Address',
            'state_id': self.states['TX'].id,
        })
        employee_change = self.env['hr.employee'].create({
            'name': 'Test Employee State Change',
            'address_id': address_ny.id,
        })
        self.assertEqual(employee_change.l10n_us_state_filing_status, 'ny_status_1')

        employee_change.address_id = address_tx
        self.assertFalse(
            employee_change.l10n_us_state_filing_status,
            "Filing status should be cleared when changing to unsupported state"
        )

    def test_correct_filing_status_preserved(self):
        """Correct filing status is preserved when it matches the state"""
        address_ny = self.env['res.partner'].create({
            'name': 'NY Address',
            'state_id': self.states['NY'].id,
        })
        employee_preserve = self.env['hr.employee'].create({
            'name': 'Test Employee Preserve',
            'address_id': address_ny.id,
        })
        employee_preserve.l10n_us_state_filing_status = 'ny_status_2'
        employee_version = employee_preserve.version_id
        self.env.add_to_compute(employee_version._fields['l10n_us_state_filing_status'], employee_version)
        self.assertEqual(
            employee_preserve.l10n_us_state_filing_status,
            'ny_status_2',
            "Correct filing status matching the state should be preserved"
        )

    def test_city_domain_for_state(self):
        """ Test that only cities from selected state appear in city domain """
        version = self.env['hr.version'].create({
            'name': 'Test US Employee',
            'private_country_id': self.country_us.id,
            'private_state_id': self.state_ca.id,
        })

        domain = [
            ('country_id', '=', version.private_country_id.id),
            ('state_id', '=', version.private_state_id.id),
        ]
        matching_cities = self.env['res.city'].search(domain)

        self.assertIn(self.city_la, matching_cities)
