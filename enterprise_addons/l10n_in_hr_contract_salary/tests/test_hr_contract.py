# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
import json
from odoo.addons.hr_contract_salary.utils.hr_version import hr_version_context
from odoo.tools import file_open
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrContractSalarySimulation(TransactionCase):

    def test_generate_salary_simulation_payslip_skips_tds_estimation(self):
        """
        Generating a simulation payslip for an Indian employee must skip
        the yearly TDS estimation.
        """
        company_in = self.env['res.company'].create({
            'name': 'Company IN',
            'country_id': self.env.ref('base.in').id,
        })
        structure_type = self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp_pay')
        employee = self.env['hr.employee'].create({
            'name': 'Indian Employee',
            'company_id': company_in.id,
            'structure_type_id': structure_type.id,
            'contract_date_start': date.today(),
            'wage': 50000,
        })
        with hr_version_context(employee.version_id) as version:
            payslip = version._generate_salary_simulation_payslip()
        self.assertFalse(payslip.env.context.get('calculate_tds', True),
            "Simulation payslip should be generated with the TDS estimation disabled")


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrContractConfigurator(HttpCase):

    def setUp(self):
        super().setUp()

        self.company_in = self.env['res.company'].create({
            'name': 'Company IN',
            'country_id': self.env.ref('base.in').id,
            'l10n_in_provident_fund': True,
        })
        self.job = self.env['hr.job'].create({
            'name': 'Indian job',
            'company_id': self.company_in.id,
        })
        self.department = self.env['hr.department'].create({
            'name': 'Dept',
            'company_id': self.company_in.id,
        })

        with file_open('hr_contract_salary/static/src/demo/employee_contract.pdf', 'rb') as f:
            pdf_content = f.read()
        attachment = self.env['ir.attachment'].create({
            'type': 'binary',
            'raw': pdf_content,
            'name': 'test_employee_contract.pdf',
        })
        sign_template = self.env['sign.template'].create({
        'name': 'Employee Contract Template',
        })
        sign_document = self.env['sign.document'].create({
            'attachment_id': attachment.id,
            'template_id': sign_template.id,
        })
        self.env['sign.item'].create({
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'required': True,
            'responsible_id': self.env.ref('hr_sign.sign_item_role_employee_signatory').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.158,
            'document_id': sign_document.id,
            'width': 0.150,
            'height': 0.015,
        })
        structure_type = self.env.ref(
            'l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp_pay'
        )
        self.env.ref('base.user_admin').write({
            'email': 'admin@example.com',
        })
        self.env['hr.version'].create({
            'name': 'Contract Template',
            'wage': 50000,
            'structure_type_id': structure_type.id,
            'job_id': self.job.id,
            'sign_template_id': sign_template.id,
            'company_id': self.company_in.id,
            'hr_responsible_id': self.env.ref('base.user_admin').id,
        })
        self.applicant = self.env['hr.applicant'].create({
            'partner_name': 'Test app',
            'job_id': self.job.id,
        })
        self.applicant.action_generate_offer()
        self.offer = self.env['hr.contract.salary.offer'].search([
            ('applicant_id', '=', self.applicant.id)
        ])
        self.benefits = {
            'version': {
                'wage': 50000.0,
                'final_yearly_costs': 655200.0,
                'l10n_in_medical_insurance': "",
                'fold_l10n_in_insured_spouse': False,
                'l10n_in_insured_spouse': "",
                'fold_l10n_in_insured_first_children': False,
                'l10n_in_insured_first_children': "",
                'fold_l10n_in_insured_second_children': False,
                'l10n_in_insured_second_children': "",
                'l10n_in_pf_employee_amount_radio': 1.0,
                'l10n_in_pf_employee_amount': 1800.0,
                'l10n_in_phone_subscription_radio': 1.0,
                'l10n_in_phone_subscription': 1100.0,
                'l10n_in_internet_subscription_radio': 1.0,
                'l10n_in_internet_subscription': 500.0,
                'l10n_in_meal_voucher_amount_radio': 1.0,
                'l10n_in_meal_voucher_amount': 1200.0,
                'l10n_in_company_transport_radio': 1.0,
                'l10n_in_company_transport': 1800.0,
                'holidays_slider': 0,
                'holidays': 0,
            },
            'version_personal': {
                'private_city': 'Test City',
                'private_country_id': self.env.ref("base.in").id,
                'private_street': 'Test Street',
            },
            'employee': {
                'name': 'Sample 1',
                'job_title': 'Indian job',
                'employee_job_id': self.job.id,
                'department_id': self.department.id,
                'private_email': 'sdf@ksa.com',
            },
            'address': {},
            'bank_account': {'account_number': ''},
        }

    def test_salary_configurator_basic_salary_stability(self):
        data = {
            "params": {
                "offer_id": self.offer.id,
                "benefits": self.benefits,
                "token": self.offer.access_token,
            }
        }
        res = self.url_open("/salary_package/update_salary", json=data)
        result_before = json.loads(res.content)["result"]
        basic_before = next(line for line in result_before['payslip_lines'] if line[2] == 'BASIC')[1]
        gross_before = next(line for line in result_before['payslip_lines'] if line[2] == 'GROSS')[1]
        net_before = next(line for line in result_before['payslip_lines'] if line[2] == 'NET')[1]
        # Remove a benefit
        self.benefits['version']['l10n_in_phone_subscription_radio'] = 0.0
        self.benefits['version']['l10n_in_phone_subscription'] = 0.0
        data["params"]["benefits"] = self.benefits
        res = self.url_open("/salary_package/update_salary", json=data)
        result_after = json.loads(res.content)["result"]

        basic_after = next(line for line in result_after['payslip_lines'] if line[2] == 'BASIC')[1]
        gross_after = next(line for line in result_after['payslip_lines'] if line[2] == 'GROSS')[1]
        net_after = next(line for line in result_after['payslip_lines'] if line[2] == 'NET')[1]

        self.assertEqual(float(basic_before), float(basic_after),
            "Basic salary must remain unchanged when benefits are removed")
        self.assertTrue(float(gross_after) < float(gross_before),
            "Gross/Taxable salary should decrease when benefits are removed")
        self.assertTrue(float(net_after) < float(net_before),
            "Net salary should decrease when benefits are removed")

    def test_salary_configurator_no_error_on_reopen_with_empty_fields(self):
        """
        Test that reopening the salary configurator for the same applicant
        does not raise an error when unique fields (UAN/PAN/ESIC) are left
        empty on the first submission.
        """
        self.benefits['employee'].update({
            'l10n_in_pan': '',
            'l10n_in_uan': '',
            'l10n_in_esic_number': '',
        })
        data = {
            'params': {
                'offer_id': self.offer.id,
                'benefits': self.benefits,
                'token': self.offer.access_token,
            }
        }
        res = self.url_open('/salary_package/submit', json=data)
        result = json.loads(res.content)['result']
        self.assertFalse(
            result.get('error'),
            "First submission should not raise an error"
        )
        self.offer.unlink()
        self.applicant.action_generate_offer()
        self.offer = self.env['hr.contract.salary.offer'].search([
            ('applicant_id', '=', self.applicant.id)
        ])
        data['params']['offer_id'] = self.offer.id
        data['params']['token'] = self.offer.access_token

        res = self.url_open('/salary_package/submit', json=data)
        result = json.loads(res.content)['result']
        self.assertFalse(
            result.get('error'),
            "Second submission should not raise a unique constraint error "
            "when statutory fields are empty"
        )

    def test_salary_configurator_hides_pf_ui_when_disabled(self):
        self.company_in.l10n_in_provident_fund = False

        res = self.url_open(f'/salary_package/simulation/offer/{self.offer.id}?token={self.offer.access_token}')
        content = res.content.decode()

        self.assertEqual(res.status_code, 200)
        self.assertIn('id="hr_cs_form"', content)
        self.assertIn('Our Offer', content)
        self.assertIn('Monthly Benefit in Kind', content)
        self.assertNotIn('Provident Fund', content)
        self.assertNotIn('Extra Benefits', content)
        self.assertNotIn('l10n_in_pf_employee_amount', content)
