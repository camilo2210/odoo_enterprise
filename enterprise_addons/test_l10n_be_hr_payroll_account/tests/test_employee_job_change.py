# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from freezegun import freeze_time

from odoo import Command
import odoo.tests
from . import common


@odoo.tests.tagged('-at_install', 'post_install', 'salary')
class TestEmployeeJobChange(common.TestPayrollAccountCommon):

    @classmethod
    @freeze_time('2022-01-01 09:00:00')
    def setUpClass(cls):
        super().setUpClass()

        cls.env.ref('base.user_admin').group_ids |= cls.env.ref('hr.group_hr_user')
        cls.new_job = cls.env['hr.job'].create({
            'name': 'Senior Developer BE',
            'company_id': cls.company_id.id,
            'contract_template_id': cls.senior_dev_contract.id,
        })
        partner = cls.env['res.partner'].create({
            'name': 'Jean Jasse',
            'street': 'La rue, 15',
            'city': 'Brussels',
            'country_id': cls.env.ref('base.be').id,
            'zip': '0348',
            'lang': 'en_US',
            'phone': '+32 2 290 34 90',
            'email': 'jeanjasse@doublehelice.be',
        })
        work_contact = cls.env['res.partner'].sudo().create({
            'email': 'jeanjasse@doublehelice.be',
            'phone': '+32 2 290 34 90',
            'name': 'Jean Jasse',
            'company_id': cls.company_id.id,
        })
        account = cls.env['res.partner.bank'].create({
            'account_number': 'BE02151804051200',
            'bank_name': 'ING',
            'bank_bic': 'BBRUBEBB',
            'partner_id': partner.id,
            'company_id': cls.company_id.id,
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Jean Jasse',
            'company_id': cls.company_id.id,
            'country_id': cls.env.ref('base.be').id,
            'bank_account_ids':  [Command.link(account.id)],
            'children': 0,
            'km_home_work': 0,
            'place_of_birth': 'Charleroi',
            'country_of_birth': cls.env.ref('base.be').id,
            'niss': '88051056350',
            'certificate': 'master',
            'study_field': 'Civil Engineering',
            'work_contact_id': work_contact.id,
            'work_email': 'jeanjasse@doublehelice.be',
            'l10n_be_scale_seniority': 1,
            'emergency_contact': 'Caballero',
            'emergency_phone': '+32 2 290 34 90',
            'private_street': 'La rue, 15',
            'private_city': 'Brussels',
            'private_country_id': cls.env.ref('base.be').id,
            'private_zip': '0348',
            'private_phone': '+32 2 290 34 90',
            'private_email': 'jeanjasse@doublehelice.be',
            'lang': 'en_US',
            'id_card': cls.pdf_content,
            'wage': 3000,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'contract_template_id': cls.new_dev_contract.id,
            'sign_template_id': cls.template.id,
            'ip_wage_rate': 0.25,
            'internet': 0,
            'date_version': datetime.date(2020, 1, 1),
            'contract_date_start': datetime.date(2020, 1, 1),
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })
        cls.env['res.users'].create({
            'create_employee_id': cls.employee.id,
            'employee_id': cls.employee.id,
            'name': cls.employee.name,
            'email': 'jeanjasse@doublehelice.be',
            'login': 'jeanjasse',
            'password': 'jeanjasse',
            'company_id': cls.company_id.id,
            'company_ids': cls.company_id.ids,
        })
        cls.senior_dev_contract.l10n_be_joint_committee_id = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.env.flush_all()

    def test_employee_job_change(self):
        # This test checks if an employee changing jobs while staying in the company correctly gets
        # the values of the new job instead of the values of the old one.
        # This test also ensure that every required values that can be prefilled using the
        # employee's data is indeed prefilled.
        # Employee's New job has been changed here, because field has been removed from the tour.
        self.employee.job_id = self.new_job.id
        with freeze_time("2022-01-01"):
            self.start_tour("/odoo", 'hr_contract_salary_tour_job_change', login='admin')
        job_changing_employee = self.env['hr.employee'].search([('name', '=', 'Jean Jasse')])
        new_version = self.env['hr.version'].search([
            ('employee_id', '=', job_changing_employee.id),
            ('active', '=', False),
        ])
        self.assertTrue(job_changing_employee.active, 'Employee is active')
        self.assertTrue(new_version.metro_transport_employee_amount, 300)
        self.assertTrue(new_version.metro_transport_reimbursed_amount, (300 / 12) * 0.718)
        self.assertTrue(new_version.metro_transport_periodicity, 'yearly')
        self.assertEqual(new_version.ip_wage_rate, 0.5, 'The new contract should have an ip_wage_rate of 0.5 (50%)')
