# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests import tagged
from ...sign.tests.sign_controller_common import TestSignControllerCommon
from ..controllers.main import SignContract
from ...hr_contract_salary.controllers import main


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestContractSignController(TestSignControllerCommon, TestBelgiumCommon):
    def setUp(self):
        super().setUp()
        SignContract.__bases__ = (main.SignContract,)
        self.SignController = SignContract()

        partner = self.env['res.partner'].create({
            'name': "Hey Partner",
            'email': 'jack.sparrow@example.me',
        })
        self.user1 = self.env['res.users'].create([
            {
                'name': 'User 1',
                'login': 'user1',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
                'notification_type': 'email',
                'partner_id': partner.id,
            },
        ])
        self.emp1 = self.env['hr.employee'].create([
            {
                "name": "Arthur Morgan",
                "user_id": self.user1.id,
            },
        ])

    def test_sign_document_linked_to_an_offer(self):

        sign_request = self.create_sign_request_1_role_sms_auth(self.user1.partner_id, self.user1.partner_id)
        sign_request_item = sign_request.request_item_ids[0]

        # Prepare contract variables
        company = self.env['res.company'].create({
            'name': 'Test Belgium Company',
            'country_id': self.env.ref('base.be').id,
        })
        company.current_payroll_config_id.l10n_be_employer_category_id = self.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010')
        self.emp1.work_contact_id = self.partner_2.id
        self.emp1.company_id = company.id
        self.emp1.country_code = 'BE'
        version = self.env['hr.version'].create({
            'name': 'Test Contract',
            'employee_id': self.emp1.id,
            'date_start': date(2025, 1, 1),
            'date_version': date(2025, 1, 1),
            'wage': 1000,
            'company_id': self.emp1.company_id.id,
            'active': False,
            'sign_template_id': sign_request.template_id.id,
            'sign_request_ids': [(4, sign_request.id)],
        })
        # Create a salary offer linked to the sign request
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.emp1.id,
            'company_id': self.emp1.company_id.id,
            'contract_template_id': version.id,
            'sign_request_ids': [(4, sign_request.id)],
            'state': 'half_signed',
        })

        sign_vals = self.create_sign_values(sign_request.template_id.sign_item_ids, sign_request_item.role_id.id)
        response = self._json_url_open(
            '/sign/sign/%d/%s' % (sign_request.id, sign_request_item.access_token),
            data={'signature': sign_vals}
        ).json()['result']

        self.assertEqual(response.get('url'), '/salary_package/thank_you/' + str(offer.id))
        self.assertTrue(response.get('success'))
        self.assertTrue(sign_request_item.state, 'completed')

    def test_sign_document_not_linked_to_an_offer(self):

        sign_request = self.create_sign_request_1_role_sms_auth(self.partner_1, self.env['res.partner'])
        sign_request_item = sign_request.request_item_ids[0]

        sign_vals = self.create_sign_values(sign_request.template_id.sign_item_ids, sign_request_item.role_id.id)
        response = self._json_url_open(
            '/sign/sign/%d/%s' % (sign_request.id, sign_request_item.access_token),
            data={'signature': sign_vals}
        ).json()['result']

        self.assertEqual(response.get('url'), None)
        self.assertTrue(response.get('success'))
        self.assertTrue(sign_request_item.state, 'completed')

    def test_onchange_fold_company_bike_depreciated_cost(self):
        self.authenticate('admin', 'admin')
        company = self.env['res.company'].create({
            'name': 'Test Belgium Company',
            'country_id': self.env.ref('base.be').id,
        })
        self.emp1.company_id = company.id
        self.emp1.country_code = 'BE'

        version = self.env['hr.version'].create({
            'name': 'Test Contract',
            'employee_id': False,
            'wage': 1000,
            'company_id': company.id,
        })
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.emp1.id,
            'company_id': company.id,
            'contract_template_id': version.id,
        })

        res = self.make_jsonrpc_request(
            '/salary_package/onchange_benefit',
            params={
                'benefit_field': 'fold_company_bike_depreciated_cost',
                'new_value': True,
                'offer_id': offer.id,
                'token': offer.access_token,
                'benefits': {'version': {}},
            }
        )

        extra_values = res.get('extra_values') or []
        self.assertEqual(
            extra_values,
            [['company_bike_depreciated_cost', 0]],
            "Should fallback extra_values to 0 when select_company_bike_depreciated_cost is missing"
        )

        brand = self.env['fleet.vehicle.model.brand'].create({'name': 'Test Bike Brand'})
        bike_model = self.env['fleet.vehicle.model'].create({
            'name': 'Test Bike Model',
            'brand_id': brand.id,
            'vehicle_type': 'bike',
            'default_recurring_cost_amount_depreciated': 150.0,
        })

        res_with_value = self.make_jsonrpc_request(
            '/salary_package/onchange_benefit',
            params={
                'benefit_field': 'fold_company_bike_depreciated_cost',
                'new_value': True,
                'offer_id': offer.id,
                'token': offer.access_token,
                'benefits': {'version': {
                    'select_company_bike_depreciated_cost': f'new-{bike_model.id}',
                }},
            }
        )

        extra_values_with_value = res_with_value.get('extra_values') or []
        self.assertEqual(
            extra_values_with_value,
            [['company_bike_depreciated_cost', 150.0]],
            "Should compute depreciated cost when select_company_bike_depreciated_cost is provided"
        )
