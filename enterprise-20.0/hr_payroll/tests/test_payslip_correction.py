# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPayslipCorrectionWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'Test Employee'})
        cls.struct_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test Type',
            'country_id': cls.env.company.country_id.id,
        })
        cls.struct_a, cls.struct_b = cls.env['hr.payroll.structure'].create([
            {'name': 'Struct A', 'type_id': cls.struct_type.id},
            {'name': 'Struct B', 'type_id': cls.struct_type.id}
        ])
        base_slip_vals = {
            'employee_id': cls.employee.id,
            'state': 'paid',
            'done_date': fields.Datetime.now() - timedelta(days=5),
        }
        slips = cls.env['hr.payslip'].create([
            {**base_slip_vals, 'name': 'S1', 'struct_id': cls.struct_a.id, 'date_from': '2026-01-01', 'date_to': '2026-01-31'},
            {**base_slip_vals, 'name': 'S2', 'struct_id': cls.struct_a.id, 'date_from': '2026-02-01', 'date_to': '2026-02-28'},
            {**base_slip_vals, 'name': 'S3', 'struct_id': cls.struct_b.id, 'date_from': '2026-01-01', 'date_to': '2026-01-31'},
        ])
        cls.slip_1 = slips[0]
        cls.employee.version_id.last_modified_date = fields.Datetime.now()

    def test_action_revert_single(self):
        wizard = self.env['hr.payslip.correction.wizard'].create({
            'employee_ids': [Command.set([self.employee.id])],
            'payslip_ids': [Command.set([self.slip_1.id])],
            'correction_choice': 'single',
        })
        wizard.action_revert_payslips()
        runs = self.env['hr.payslip.run'].search([
            ('name', 'ilike', 'Revert%'),
            ('slip_ids.employee_id', '=', self.employee.id)
        ])
        self.assertEqual(len(runs), 1)

    def test_action_correct_multi(self):
        wizard = self.env['hr.payslip.correction.wizard'].create({
            'employee_ids': [Command.set([self.employee.id])],
            'payslip_ids': [Command.set([self.slip_1.id])],
            'correction_choice': 'multi',
        })
        self.assertEqual(len(wizard.allowed_payslip_ids), 3)
        wizard.action_correct_payslips()
        runs = self.env['hr.payslip.run'].search([
            ('name', 'ilike', 'Correction%'),
            ('slip_ids.employee_id', '=', self.employee.id)
        ])
        self.assertEqual(len(runs), 2)
        run_a = runs.filtered(lambda r: r.structure_id == self.struct_a)
        self.assertIn('01/26 -> 02/26', run_a.name)

    def test_action_correct_other_company(self):
        """ Corrections must stay in the payslip's company, not in the active one. """
        company_b = self.env['res.company'].create({
            'name': 'Company B',
            'country_id': self.env.company.country_id.id,
        })
        self.env.user.company_ids = [Command.link(company_b.id)]
        employee_b = self.env['hr.employee'].with_company(company_b).create({'name': 'Employee B'})
        slip_b = self.env['hr.payslip'].with_company(company_b).create({
            'name': 'B1',
            'employee_id': employee_b.id,
            'struct_id': self.struct_a.id,
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
            'state': 'paid',
            'done_date': fields.Datetime.now() - timedelta(days=5),
        })
        self.assertEqual(slip_b.company_id, company_b)

        # the active company is not the company of the payslip being corrected
        wizard = self.env['hr.payslip.correction.wizard'].with_context(
            allowed_company_ids=[self.env.company.id, company_b.id],
        ).create({
            'employee_ids': [Command.set([employee_b.id])],
            'payslip_ids': [Command.set([slip_b.id])],
            'correction_choice': 'single',
        })
        self.assertNotEqual(wizard.env.company, company_b)
        wizard.action_correct_payslips()

        new_slips = self.env['hr.payslip'].search([('origin_payslip_id', '=', slip_b.id)])
        self.assertEqual(len(new_slips), 2)
        self.assertEqual(new_slips.company_id, company_b)
        self.assertEqual(new_slips.payslip_run_id.company_id, company_b)
