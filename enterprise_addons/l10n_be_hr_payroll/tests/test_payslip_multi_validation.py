# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayslipMultiValidation(TestPayrollCommon):

    def test_multi_payslips_validation(self):
        """
        Ensure that validating several draft payslips at once from the list view
        forwards the language wizard instead of silently leaving them in draft.
        """
        self.env['res.lang']._activate_lang('fr_BE')
        with freeze_time('2026-08-03'):
            structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
            slips = self.env['hr.payslip']
            # Three consecutive monthly payslips for the same employee.
            for month in (3, 4, 5):
                date_from = date(2026, month, 1)
                slips |= self.env['hr.payslip'].create({
                    'employee_id': self.employee_georges.id,
                    'struct_id': structure.id,
                    'version_id': self.employee_georges.version_id.id,
                    'date_from': date_from,
                    'date_to': date_from + relativedelta(months=1, day=1, days=-1),
                })
            slips.compute_sheet()
            self.employee_georges.lang = 'en_US'

            action = slips.action_validate()
            # The english speaking employee needs a belgian language first.
            self.assertEqual(action.get('res_model'), 'l10n_be.hr.payroll.employee.lang.wizard', "The language wizard should be returned to the caller.")

            wizard = self.env['l10n_be.hr.payroll.employee.lang.wizard'].with_context(**action['context']).create({})
            wizard.line_ids.lang = 'fr_BE'
            wizard.action_validate()
            self.assertEqual(set(slips.mapped('state')), {'validated'}, "Every selected payslip should be validated.")
