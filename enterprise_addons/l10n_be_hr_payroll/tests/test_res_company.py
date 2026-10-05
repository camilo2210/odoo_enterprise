from odoo.tests import TransactionCase, tagged
from datetime import date


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestResCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):

        super().setUpClass()
        cls.be_company = cls.env['res.company'].create({
            'name': 'My Belgian Company - TEST',
            'country_id': cls.env.ref('base.be').id,
        })

        cls.be_company.current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
        })

        cls.worker_type = cls.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_be_worker')
        cls.employee_type = cls.env.ref('hr.contract_type_employee')

        cls.worker_015 = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015')
        # employee 495 is not count as worker (according to Belgian definition)
        cls.employee_495 = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495')

        cls.employee = cls.env['hr.employee'].create({
            'name': "employee",
            'date_version': date(2026, 9, 1),
            'employee_type_id': cls.employee_type.id,
            'l10n_be_worker_code_id': cls.employee_495.id,
        })
        cls.worker = cls.env['hr.employee'].create({
            'name': "worker",
            'date_version': date(2026, 9, 1),
            'employee_type_id': cls.worker_type.id,
            'l10n_be_worker_code_id': cls.worker_015.id,
        })

        cls.director = cls.env['hr.employee'].create({
            'name': "Director",
            'date_version': date(2026, 9, 1),
        })
        cls.env['l10n.be.joint.committee'].with_context(active_test=False).search([('egov3_code', '=', '999')], limit=1).write({'active': True})
        cls.director_jc = cls.env['l10n.be.joint.committee'].search([('egov3_code', '=', '999')], limit=1)

    def test_compute_l10n_be_has_employees(self):
        self.assertFalse(self.be_company.l10n_be_has_employees)

        self.director.write({'company_id': self.be_company.id})
        self.director.version_ids.write({'l10n_be_joint_committee_id': self.director_jc.id})
        self.be_company.invalidate_recordset(['l10n_be_has_employees'])
        self.assertFalse(self.be_company.l10n_be_has_employees)

        self.worker.write({'company_id': self.be_company.id})
        self.be_company.invalidate_recordset(['l10n_be_has_employees'])
        self.assertTrue(self.be_company.l10n_be_has_employees)

        self.employee.write({'company_id': self.be_company.id})
        self.be_company.invalidate_recordset(['l10n_be_has_employees'])
        self.assertTrue(self.be_company.l10n_be_has_employees)

    def test_compute_l10n_be_has_workers(self):
        self.assertFalse(self.be_company.l10n_be_has_workers)

        self.employee.write({'company_id': self.be_company.id})
        self.be_company.invalidate_recordset(['l10n_be_has_workers'])
        self.assertFalse(self.be_company.l10n_be_has_workers)

        self.worker.write({'company_id': self.be_company.id})
        self.be_company.invalidate_recordset(['l10n_be_has_workers'])
        self.assertTrue(self.be_company.l10n_be_has_workers)
