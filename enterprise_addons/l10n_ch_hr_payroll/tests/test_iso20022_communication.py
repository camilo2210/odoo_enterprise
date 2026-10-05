# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.addons.l10n_ch_hr_payroll.models.hr_payslip import HrPayslip as ChHrPayslip
from odoo.tests.common import tagged, TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestIso20022Communication(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ch_company = cls.env['res.company'].create({
            'name': "CH Company",
            'country_id': cls.env.ref('base.ch').id,
        })

        cls.ch_employee = cls.env['hr.employee'].create({
            'name': "Test",
            'company_id': cls.ch_company.id,
        })

        cls.ch_contract = cls.ch_employee.create_version({
            'contract_date_start': fields.Date.today(),
            'contract_date_end': False,
            'date_version': fields.Date.today(),
        })

        cls.work_contact = cls.env['res.partner'].create({'name': "Test"})
        cls.ch_employee.work_contact_id = cls.work_contact

        cls.payslip = cls.env['hr.payslip'].create({
            'name': "Test Payslip",
            'employee_id': cls.ch_employee.id,
            'version_id': cls.ch_contract.id,
            'company_id': cls.ch_company.id,
            'date_from': fields.Date.today(),
            'date_to': fields.Date.today(),
        })

    def test_revolut_communication(self):
        # The override in this module is currently shadowed by the base implementation of
        # hr_payroll_account_iso20022 (sibling modules extending hr.payslip, this one loads
        # first), so regular method dispatch never reaches it. Call this module's
        # implementation directly to cover its logic until the shadowing is fixed.
        revolut_by_bic, revolut_by_name = self.env['res.partner.bank'].create([
            {
                'account_number': 'CH9300762011623852957',
                'partner_id': self.work_contact.id,
                'bank_name': 'Some Bank',
                'bank_bic': 'REVOLT21',
            },
            {
                'account_number': 'CH5604835012345678009',
                'partner_id': self.work_contact.id,
                'bank_name': 'Revolut Bank UAB',
            },
        ])
        self.ch_employee.write({
            'bank_account_ids': [Command.link(revolut_by_bic.id), Command.link(revolut_by_name.id)],
            'l10n_ch_legal_first_name': 'Jean',
            'l10n_ch_legal_last_name': 'Dupont',
        })
        ch_get_communication = ChHrPayslip._get_iso20022_communication
        self.assertEqual(ch_get_communication(self.payslip, revolut_by_bic), 'Jean Dupont, CH')
        self.assertEqual(ch_get_communication(self.payslip, revolut_by_name), 'Jean Dupont, CH')
