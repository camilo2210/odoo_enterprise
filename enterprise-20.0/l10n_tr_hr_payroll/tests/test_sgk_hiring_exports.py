# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo import Command
from odoo.tests import common, tagged
from odoo.exceptions import UserError

from .common import TestL10nTrHrPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSGKHiringExports(TestL10nTrHrPayrollCommon, common.HttpCase):

    def test_company_required_field_not_found(self):
        #   =================================================================================================
        #   | This test checks that company should have set required field to generate a SGK hiring report  |
        #   =================================================================================================
        fatma_hiring_xml_report = self.env['l10n.tr.sgk.hiring.wizard'].create({
            'employee_ids': [
                Command.link(self.employee_fatma.id),
            ],
        })
        with self.assertRaises(UserError) as error_msg:
            fatma_hiring_xml_report.action_generate_report()

        company_field_labels = self.turkey_company._fields
        company_required_fields = ['l10n_tr_sgk_intermediary_code', 'l10n_tr_sgk_workspace_registration_no']
        for field in company_required_fields:
            if not self.turkey_company[field]:
                self.assertIn(company_field_labels[field].string, str(error_msg.exception))

    def test_employee_required_field_not_found(self):
        #   =================================================================================================
        #   | This test checks that employee should have set required field to generate a SGK hiring report |
        #   =================================================================================================
        self.turkey_company.write({
            'l10n_tr_sgk_workspace_registration_no': '123456789012345678901',
            'l10n_tr_sgk_intermediary_code': '123',
        })
        ahmed_hiring_xml_report = self.env['l10n.tr.sgk.hiring.wizard'].create({
            'employee_ids': [
                Command.link(self.employee_ahmed.id),
            ],
        })
        with self.assertRaises(UserError) as error_msg:
            ahmed_hiring_xml_report.action_generate_report()

        employee_field_labels = self.employee_ahmed._fields
        employee_required_fields = [
            'certificate', 'identification_id', 'l10n_tr_first_name', 'l10n_tr_last_name', 'l10n_tr_insurance_type',
            'l10n_tr_graduation_year', 'l10n_tr_labour_sector', 'l10n_tr_occupational_code', 'l10n_tr_job_code',
        ]
        for field in employee_required_fields:
            if not self.employee_ahmed[field]:
                self.assertIn(employee_field_labels[field].string, str(error_msg.exception))

    def test_export_sgk_hiring_report_xml(self):
        #   =================================================================================================
        #   | This test checks that all the required tags and tag attributes should be present in XML file  |
        #   =================================================================================================
        self.turkey_company.write({
            'l10n_tr_sgk_workspace_registration_no': '123456789012345678901',
            'l10n_tr_sgk_intermediary_code': '123',
        })
        fatma_hiring_xml_report = self.env['l10n.tr.sgk.hiring.wizard'].create({
            'employee_ids': [
                Command.link(self.employee_fatma.id),
            ],
        })
        fatma_hiring_xml_report.action_generate_report()
        root = etree.fromstring(fatma_hiring_xml_report.xml_file.content)
        # root
        self.assertEqual(root.tag, 'SGK4AISEGIRIS')

        # root[0] -> ISYERI(company details)
        self.assertEqual(root[0].tag, 'ISYERI')
        actual_key_value = {
            'ISYERIARACINO': self.turkey_company.l10n_tr_sgk_intermediary_code,
            'ISYERISICIL': self.turkey_company.l10n_tr_sgk_workspace_registration_no,
            'ISYERIUNVAN': self.turkey_company.name,
        }
        self.assertTrue(actual_key_value.items() <= dict(root[0].attrib).items())
        self.assertTrue('NAKILGELDIGIISYERISICIL' in root[0].attrib)
        self.assertTrue('ISYERIADRES' in root[0].attrib)

        # root[1] -> SIGORTALILAR | root[1][0] = SIGORTALI
        self.assertEqual(root[1].tag, 'SIGORTALILAR')
        self.assertEqual(root[1][0].tag, 'SIGORTALI')
        actual_key_value = {
            'TCKNO': self.employee_fatma.identification_id,
            'ISEGIRISTARIHI': self.employee_fatma._get_first_version_date().strftime('%Y-%m-%d'),
            'OZURLUKODU': 'E' if self.employee_fatma.disabled else 'H',
            'MEZUNIYETBOLUMU': self.employee_fatma.study_field,
            'AD': self.employee_fatma.l10n_tr_first_name,
            'SOYAD': self.employee_fatma.l10n_tr_last_name,
            'SIGORTAKOLU': self.employee_fatma.l10n_tr_insurance_type,
            'ESKIHUKUMLU': 'E' if self.employee_fatma.l10n_tr_is_ex_convict else 'H',
            'OGRENIMKODU': self.employee_fatma._l10n_tr_get_certificate_report_value(),
            'MEZUNIYETYILI': self.employee_fatma.l10n_tr_graduation_year,
            'CSGBISKOLU': self.employee_fatma.l10n_tr_labour_sector,
            'MESLEKKODU': self.employee_fatma.l10n_tr_occupational_code,
            'GOREVKODU': self.employee_fatma.l10n_tr_job_code,
        }
        self.assertEqual(root[1][0].attrib, actual_key_value)
