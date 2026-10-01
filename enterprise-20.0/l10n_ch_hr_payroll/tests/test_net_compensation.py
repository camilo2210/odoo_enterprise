# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import TestSwissdecCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'swissdec_payroll')
class TestNetCompensation(TestSwissdecCommon):
    """ Automatic wage type 4900 computation for the net compensation wage types. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.muster_ag_company
        with freeze_time("2023-02-28"):
            cls.location_unit_lu = cls.env['l10n.ch.location.unit'].create({
                "company_id": company.id,
                "partner_id": cls.env['res.partner'].create({
                    'name': 'Hauptsitz',
                    'street': 'Bahnhofstrasse 1',
                    'zip': '6003',
                    'city': 'Luzern',
                    'country_id': cls.env.ref('base.ch').id,
                }).id,
                "bur_ree_number": "A92978109",
                "canton": 'LU',
                "dpi_number": '158.87.6',
                "municipality": '1061',
                "weekly_hours": 40,
                "weekly_lessons": 20,
            })
            cls.location_unit_ti = cls.env['l10n.ch.location.unit'].create({
                "company_id": company.id,
                "partner_id": cls.env['res.partner'].create({
                    'name': 'Beratung',
                    'street': 'Via Canonico Ghiringhelli 19',
                    'zip': '6500',
                    'city': 'Bellinzona',
                    'country_id': cls.env.ref('base.ch').id,
                }).id,
                "bur_ree_number": "A92978114",
                "canton": 'TI',
                "dpi_number": '83189.7',
                "municipality": '5002',
                "weekly_hours": 40,
                "weekly_lessons": 20,
            })
            cls.social_insurance = cls.env['l10n.ch.social.insurance'].create({
                'name': 'AVS 2021',
                'member_number': '7019.2',
                'company_id': company.id,
                'insurance_code': '003.000',
                'age_start': 18,
                'age_stop_male': 65,
                'age_stop_female': 64,
                'avs_line_ids': [(0, 0, {
                    'date_from': date(2021, 1, 1),
                    'employer_rate': 5.3,
                    'employee_rate': 5.3,
                })],
                'ac_line_ids': [(0, 0, {
                    'date_from': date(2021, 1, 1),
                    'employer_rate': 1.1,
                    'employee_rate': 1.1,
                    'employee_additional_rate': 0,
                    'employer_additional_rate': 0,
                })],
                'l10n_ch_avs_rente_ids': [(0, 0, {
                    'date_from': date(2021, 1, 1),
                    'amount': 1400,
                })],
                'l10n_ch_avs_ac_threshold_ids': [(0, 0, {
                    'date_from': date(2021, 1, 1),
                    'amount': 148200,
                })],
                'l10n_ch_avs_acc_threshold_ids': [(0, 0, {
                    'date_from': date(2021, 1, 1),
                    'amount': 370500,
                })],
            })
            common_employee_vals = {
                'company_id': company.id,
                'date_version': date(2022, 1, 1),
                'contract_date_start': date(2022, 1, 1),
                'structure_type_id': cls.env.ref('l10n_ch_hr_payroll.structure_type_employee_ch').id,
                'wage_type': "monthly",
                'l10n_ch_has_monthly': True,
                'l10n_ch_social_insurance_id': cls.social_insurance.id,
            }
            # Swiss resident, no source tax
            cls.employee_ch = cls.env['hr.employee'].create({
                **common_employee_vals,
                'name': "Nathalie Ziegler",
                'country_id': cls.env.ref('base.ch').id,
                'l10n_ch_sv_as_number': '756.3552.6511.80',
                'birthday': date(1990, 4, 15),
                'marital': 'single',
                'l10n_ch_marital_from': date(1990, 4, 15),
                'private_street': 'Museggstrasse 4',
                'private_zip': '6004',
                'private_city': 'Luzern',
                'private_country_id': cls.env.ref('base.ch').id,
                'l10n_ch_municipality': '1061',
                'l10n_ch_canton': 'LU',
                'wage': 6000,
                'l10n_ch_location_unit_id': cls.location_unit_lu.id,
            })
            # Source tax, monthly model (LU)
            cls.employee_is = cls.env['hr.employee'].create({
                **common_employee_vals,
                'name': "Anna Berger",
                'country_id': cls.env.ref('base.de').id,
                'l10n_ch_sv_as_number': '756.1927.3247.52',
                'birthday': date(1977, 7, 13),
                'marital': 'single',
                'l10n_ch_marital_from': date(1977, 7, 13),
                'private_street': 'Seestrasse 5',
                'private_zip': '6353',
                'private_city': 'Weggis',
                'private_country_id': cls.env.ref('base.ch').id,
                'l10n_ch_municipality': '1069',
                'l10n_ch_canton': 'LU',
                'l10n_ch_residence_category': 'annual-B',
                'l10n_ch_religious_denomination': 'romanCatholic',
                'l10n_ch_tax_scale_type': 'TaxAtSourceCode',
                'l10n_ch_tax_scale': 'A',
                'l10n_ch_has_withholding_tax': True,
                'wage': 7000,
                'l10n_ch_location_unit_id': cls.location_unit_lu.id,
            })
            # Source tax, yearly model (TI)
            cls.employee_is_yearly = cls.env['hr.employee'].create({
                **common_employee_vals,
                'name': "Elisa Bianchi",
                'country_id': cls.env.ref('base.it').id,
                'l10n_ch_sv_as_number': '756.6319.2565.36',
                'birthday': date(1997, 6, 6),
                'marital': 'single',
                'l10n_ch_marital_from': date(1997, 6, 6),
                'private_street': 'Via Serafino Balestra 9',
                'private_zip': '6900',
                'private_city': 'Lugano',
                'private_country_id': cls.env.ref('base.ch').id,
                'l10n_ch_municipality': '5192',
                'l10n_ch_canton': 'TI',
                'l10n_ch_residence_category': 'annual-B',
                'l10n_ch_religious_denomination': 'romanCatholic',
                'l10n_ch_tax_scale_type': 'TaxAtSourceCode',
                'l10n_ch_tax_scale': 'A',
                'l10n_ch_has_withholding_tax': True,
                'wage': 7000,
                'l10n_ch_location_unit_id': cls.location_unit_ti.id,
            })

    def _create_payslip(self, employee):
        return self.env['hr.payslip'].create({
            'name': f"Payslip {employee.name}",
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'struct_id': self.env.ref('l10n_ch_hr_payroll.hr_payroll_structure_ch_elm').id,
            'date_from': date(2023, 2, 1),
            'date_to': date(2023, 2, 28),
        })

    def _add_inputs(self, payslip, amounts_by_code):
        payslip.write({'input_line_ids': [(0, 0, {
            'salary_rule_id': self.env.ref(f"l10n_ch_hr_payroll.l10n_ch_elm_{code.removeprefix('WT_').lower()}").id,
            'amount': amount,
        }) for code, amount in amounts_by_code.items()]})

    def _line_total(self, payslip, code):
        return sum(payslip.line_ids.filtered(lambda l: l.code == code).mapped('total'))

    @freeze_time("2023-02-28")
    def test_01_net_compensation_social_clawback(self):
        payslip = self._create_payslip(self.employee_ch)
        payslip.compute_sheet()
        net_reference = self._line_total(payslip, 'NET')
        self.assertTrue(net_reference, "Reference payslip should have a Net Paid")

        self._add_inputs(payslip, {'WT_2035_NET': 3000})
        payslip.compute_sheet()

        self.assertAlmostEqual(self._line_total(payslip, 'WT_2035_NET'), 3000, 2)
        self.assertAlmostEqual(self._line_total(payslip, 'WT_2050'), -3000, 2)
        compensation = self._line_total(payslip, 'WT_4900')
        self.assertLess(compensation, 0, "The employee's contribution windfall must be clawed back")
        self.assertAlmostEqual(self._line_total(payslip, 'NET'), net_reference, delta=0.051)

    @freeze_time("2023-02-28")
    def test_02_net_compensation_neutral_wage_type(self):
        payslip = self._create_payslip(self.employee_ch)
        payslip.compute_sheet()
        net_reference = self._line_total(payslip, 'NET')

        self._add_inputs(payslip, {'WT_2000_NET': 3000})
        payslip.compute_sheet()

        self.assertAlmostEqual(self._line_total(payslip, 'WT_4900'), 0, 2)
        self.assertAlmostEqual(self._line_total(payslip, 'NET'), net_reference, delta=0.051)

    @freeze_time("2023-02-28")
    def test_03_net_compensation_source_tax_monthly(self):
        payslip = self._create_payslip(self.employee_is)
        payslip.compute_sheet()
        self.assertTrue(payslip.l10n_ch_is_code, "The employee should be subject to source tax")
        self.assertEqual(payslip.l10n_ch_is_model, 'monthly')
        self.assertTrue(self._line_total(payslip, 'IS'), "A source tax amount should be withheld")
        net_reference = self._line_total(payslip, 'NET')

        self._add_inputs(payslip, {'WT_2035_NET': 3000})
        payslip.compute_sheet()

        self.assertTrue(self._line_total(payslip, 'WT_4900'))
        self.assertAlmostEqual(self._line_total(payslip, 'NET'), net_reference, delta=0.051)

    @freeze_time("2023-02-28")
    def test_04_net_compensation_source_tax_yearly_idempotent(self):
        payslip = self._create_payslip(self.employee_is_yearly)
        payslip.compute_sheet()
        self.assertTrue(payslip.l10n_ch_is_code, "The employee should be subject to source tax")
        self.assertEqual(payslip.l10n_ch_is_model, 'yearly')
        net_reference = self._line_total(payslip, 'NET')

        self._add_inputs(payslip, {'WT_2035_NET': 2500})
        payslip.compute_sheet()
        compensation = self._line_total(payslip, 'WT_4900')
        log_line_count = len(payslip.l10n_ch_is_log_line_ids)
        self.assertAlmostEqual(self._line_total(payslip, 'NET'), net_reference, delta=0.051)

        payslip.compute_sheet()
        self.assertAlmostEqual(self._line_total(payslip, 'WT_4900'), compensation, 2)
        self.assertEqual(len(payslip.l10n_ch_is_log_line_ids), log_line_count)

    @freeze_time("2023-02-28")
    def test_05_net_compensation_manual_4900_wins(self):
        payslip = self._create_payslip(self.employee_ch)
        self._add_inputs(payslip, {'WT_2035_NET': 3000, 'WT_4900': 500})
        payslip.compute_sheet()
        self.assertAlmostEqual(self._line_total(payslip, 'WT_4900'), 500, 2)

    @freeze_time("2023-02-28")
    def test_06_net_compensation_manual_2050_blocks(self):
        payslip = self._create_payslip(self.employee_ch)
        self._add_inputs(payslip, {'WT_2035_NET': 3000, 'WT_2050': 1000})
        with self.assertRaises(UserError):
            payslip.compute_sheet()

    @freeze_time("2023-02-28")
    def test_07_net_compensation_evaluation_bound(self):
        payslip = self._create_payslip(self.employee_ch)
        payslip.compute_sheet()
        net_reference = self._line_total(payslip, 'NET')

        self._add_inputs(payslip, {'WT_2035_NET': 20000})
        PayslipClass = self.env.registry['hr.payslip']
        original_eval = PayslipClass._l10n_ch_eval_net
        evaluations = []

        def counting_eval(record, compensation=0.0, without_input_codes=None):
            evaluations.append(compensation)
            return original_eval(record, compensation=compensation, without_input_codes=without_input_codes)

        with patch.object(PayslipClass, '_l10n_ch_eval_net', counting_eval):
            payslip.compute_sheet()

        self.assertLessEqual(len(evaluations), 27, "The solver must converge within its evaluation budget")
        self.assertLess(self._line_total(payslip, 'WT_4900'), 0)
        self.assertAlmostEqual(self._line_total(payslip, 'NET'), net_reference, delta=0.051)
