# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tools import BinaryBytes

from .common import TestLuPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestLuSeculineReturns(TestLuPayrollCommon):

    def test_seculine_return_salman(self):
        file_content = """0;EMP123456;SEC001
1;EMP123456;EMP00000000123;202502;DOE;JOHN;SMITH
1;EMP123456;EMP00000000456;202502;LEE;SARA;KIM"""
        seculine_return = self.env['l10n.lu.seculine.returns'].create({
            'report_file': BinaryBytes(file_content.encode('utf-8')),
        })
        seculine_return.action_l10n_lu_analyze_return_file()
        self.assertEqual(seculine_return.report_type, 'salman')
        self.assertEqual(seculine_return.year, '2025')
        self.assertEqual(seculine_return.month, '02')
        self.assertMultiLineEqual(
            seculine_return.details,
            "In the DECSAL declaration of 2025-02, the following employee records are missing:\n\n"
            "- DOE JOHN\n"
            "- LEE SARA"
        )

    def test_seculine_return_salret(self):
        file_content = """0;1234567890123;654321
9;1;1;123456789;1978022001234;202506;750000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;2;1;123456789;1984093001234;202506;425000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;3;1;123456789;1982070501234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;4;1;123456789;1982070502234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;5;1;123456789;1982070503234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;6;1;123456789;1982070504234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;7;1;123456789;1982070505234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;8;1;123456789;1982070506234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;9;1;123456789;1982070507234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;10;1;123456789;1982070501834;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;11;1;123456789;1982070501934;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
9;12;1;123456789;1982070501234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4"""

        expected_details = """In the latest DECSAL declaration, the following issues were found:

- Two records are present for the employee: 1;123456789;1978022001234;202506;750000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Employer ID Number is wrong: 1;123456789;1984093001234;202506;425000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Employee ID Number is wrong: 1;123456789;1982070501234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Either duration or amount is not numeric: 1;123456789;1982070502234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Date should be AAAAMM where year is greater than 2018 and month between 1 and 12: 1;123456789;1982070503234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Unknown error code 6: 1;123456789;1982070504234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Unemployment amount is 0 but Unemployment duration is greater than 0: 1;123456789;1982070505234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Extra hours amount is 0 but Extra Hours duration is greater than 0: 1;123456789;1982070506234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Date cannot exceed previous month: 1;123456789;1982070507234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Indemnity for retired, but employee is not in an official job position: 1;123456789;1982070501834;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Total amount of hours should not exceed 372: 1;123456789;1982070501934;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4
- Date year should be higher than 2018: 1;123456789;1982070501234;202506;200000;168;0;0;0;0;0;0;0;01;30;;;;;4"""

        seculine_return = self.env['l10n.lu.seculine.returns'].create({
            'report_file': BinaryBytes(file_content.encode('utf-8')),
        })
        seculine_return.action_l10n_lu_analyze_return_file()
        self.assertEqual(seculine_return.report_type, 'salret')
        self.assertEqual(seculine_return.year, '2025')
        self.assertEqual(seculine_return.month, '06')
        self.assertEqual(seculine_return.number_of_errors, 12)
        self.assertMultiLineEqual(seculine_return.details, expected_details)
