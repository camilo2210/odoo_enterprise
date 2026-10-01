# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time
from lxml import etree
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import test_xsd
from odoo.tools.misc import file_path


class TestNlXafExportCommon(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('nl')
    def setUpClass(cls):
        super().setUpClass()

        cls.env.company.write({
            'vat': 'NL123456782B90',
        })

        products = [cls.product_a, cls.product_b]

        # Verify if the country code validation when generating a XAF report at the very least allows
        # the Netherlands itself on a partner when no XSD is downloaded
        cls.partner_a.write({'country_id': cls.env.ref('base.nl').id})

        # Create three invoices, one refund and one bill in 2019
        partner_a_invoice1 = cls.init_invoice('out_invoice', products=products)
        partner_a_invoice2 = cls.init_invoice('out_invoice', products=products)
        partner_a_invoice3 = cls.init_invoice('out_invoice', products=products)
        partner_a_refund = cls.init_invoice('out_refund', products=products)

        partner_b_bill = cls.init_invoice('in_invoice', products=products, partner=cls.partner_b)

        # Create one invoice for partner B in 2018
        partner_b_invoice1 = cls.init_invoice('out_invoice', products=products, partner=cls.partner_b, invoice_date=fields.Date.from_string('2018-01-01'))

        # Create one MISC entry in 2018
        bank_account_id = cls.company_data['default_journal_bank'].default_account_id.id
        receivable_account_id = cls.company_data['default_account_receivable'].id
        partner_a_misc = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2018-01-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 100.0, 'credit': 0.0, 'account_id': receivable_account_id, 'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0, 'credit': 100.0, 'account_id': bank_account_id, 'partner_id': cls.partner_a.id}),
            ],
        })

        # init_invoice has hardcoded 2019 year's date, we are resetting it to current year's one.
        (partner_a_invoice1 + partner_a_invoice2 + partner_a_invoice3 + partner_b_invoice1 + partner_a_refund + partner_b_bill + partner_a_misc).action_post()


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestNlXafExport(TestNlXafExportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time('2019-12-31')
    def test_xaf_export(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = self._generate_options(report, '2019-01-01', '2019-12-31')
        expected_xaf = etree.parse(file_path('l10n_nl_reports/tests/data/xaf_export.xml')).getroot()
        with self.enter_registry_test_mode():
            # Set the batch size to 10 to make sure the generator will iterate more than once.
            self.env['ir.config_parameter'].set_int('l10n_nl_reports.general_ledger_batch_size', 10)
            xaf_stream = self.env[report.custom_handler_model_name].l10n_nl_reports_get_xaf(options).get('file_content')
            generated_xaf = self.get_xml_tree_from_string(b''.join(xaf_stream))
            self.assertXmlTreeEqual(generated_xaf, expected_xaf)


@tagged('external_l10n', 'post_install', '-at_install', '-standard', 'external')
class TestNlXafExportXmlValidity(TestNlXafExportCommon):
    _test_user_groups = None  # FIXME list needed groups

    @test_xsd(url='https://www.softwarepakketten.nl/upload/auditfiles/xaf/20140402_AuditfileFinancieelVersie_3_2.zip')
    def test_xml_validity(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = self._generate_options(report, '2019-01-01', '2019-12-31')
        with self.enter_registry_test_mode():
            xaf_stream = self.env[report.custom_handler_model_name].l10n_nl_reports_get_xaf(options).get('file_content')
            generated_xaf = self.get_xml_tree_from_string(b''.join(xaf_stream))
        return generated_xaf
