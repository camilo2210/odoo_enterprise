from lxml import etree
from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged, freeze_time

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_co_edi.tests.common import TestCoEdiCommon


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCoEdiBranch(TestCoEdiCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('co')
    def setUpClass(cls):
        super().setUpClass()
        cls.other_currency = cls.setup_other_currency('EUR')

        cls.company_data['company'].write({
            'child_ids': [
                Command.create({'name': 'Branch'}),
            ],
        })
        cls.cr.precommit.run()  # load the CoA

        cls.root_company = cls.company_data['company']
        cls.branch_a = cls.root_company.child_ids
        cls.branch_data = cls.collect_company_accounting_data(cls.branch_a)
        cls.branch_data['default_journal_sale'] = cls.company_data['default_journal_sale'].copy({
            'company_id': cls.branch_a.id,
        })

        private_key = cls.root_company.l10n_co_edi_certificate_ids.private_key_id.copy({
            'company_id': cls.branch_a.id,
        })
        cls.branch_a.l10n_co_edi_certificate_ids = cls.root_company.l10n_co_edi_certificate_ids.copy({
            'company_id': cls.branch_a.id,
            'private_key_id': private_key.id,
        })
        cls.branch_a.l10n_co_edi_operation_mode_ids = cls.root_company.l10n_co_edi_operation_mode_ids.copy({
            'company_id': cls.branch_a.id,
        })
        cls.branch_a.l10n_co_edi_test_environment = cls.root_company.l10n_co_edi_test_environment

        with patch.object(cls, 'company_data', cls.branch_data):
            cls.invoice = cls._create_move(
                company_id=cls.branch_a.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': cls.product_a.id,
                        'price_unit': 100,
                        'discount': 10,
                    }),
                ],
            )

    def test_branch_node_information(self):
        """
            The company info added in the XML (PartyName) is the parent company's,
            not the branch's
            Steps to reproduce:
            - Use Odoo 19.0
            - Install l10n_co_dian.
            - Set up a branch under a Colombian company with its own
              company data, DIAN certificates, and journals containing
              DIAN resolution fields.
            - Switch to this branch as your only active company.
            - Confirm an invoice (Accounting > Customers > Invoices).
            - Click Send, tick the DIAN checkbox, and send.
            - FAHJ34b error appears, referring to the PartyName
        """
        self.assertEqual(self.root_company.street, 'CL 12A')
        with self._disable_get_acquirer_call():
            xml = self.env['account.edi.xml.ubl_dian'].with_company(self.branch_a)._export_invoice(self.invoice)[0].decode()
        xml_tree = etree.fromstring(xml)
        for selector in ('PartyName', 'PartyTaxScheme', 'PartyLegalEntity', 'Contact'):
            node = xml_tree.find(f'./{{*}}AccountingSupplierParty/{{*}}Party/{{*}}{selector}')[0]
            self.assertEqual(node.text, self.root_company.name)
