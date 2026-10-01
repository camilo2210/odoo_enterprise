# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo.addons.account.tests.common import skip_unless_external
from odoo.tests import tagged
from odoo.addons.l10n_ar_edi.tests.common import TestArEdiMockedCommon
from odoo import Command
from datetime import date

_logger = logging.getLogger(__name__)


@tagged("post_install", "post_install_l10n", "-at_install", *TestArEdiMockedCommon.extra_tags)
class TestArEdiMocked(TestArEdiMockedCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestArEdiMockedCommon.setup_afip_ws('wsfe')
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.res_partner_adhoc
        cls.journal = cls._create_journal('wsfe')
        cls.document_type.update({
            'debit_note_a': cls.env.ref('l10n_ar.dc_a_nd'),
        })

    @skip_unless_external
    def test_01_invoice_a_product(self):
        with self.patch_client([('FECAESolicitar', 'FECAESolicitar-final', 'FECAESolicitar-final')]):
            self._test_ar_edi_flow('', 'invoice', 'a', 'product')

    @skip_unless_external
    def test_02_credit_note_standalone(self):
        ''' Test the success of issuing a credit note without an original invoice linked'''
        credit_note = self.env['account.move'].create({
            'company_id': self.company_ri.id,
            'move_type': 'out_refund',
            'partner_id': self.partner.id,
            'l10n_latam_document_type_id': self.document_type['credit_note_a'].id,
            'journal_id': self.journal.id,
            'l10n_ar_afip_asoc_period_start': date(2025, 10, 1),
            'l10n_ar_afip_asoc_period_end': date(2025, 10, 31),
            'line_ids': [Command.create({'product_id': self.product_iva_21.id, 'quantity': 1})]
        })
        expected_document = self.document_type['credit_note_a']
        self.assertEqual(credit_note.l10n_latam_document_type_id.display_name, expected_document.display_name, 'The document should be %s' % expected_document.display_name)
        with self.patch_client([('FECAESolicitar', 'FECAESolicitar-credit-note-request', 'FECAESolicitar-credit-note-response')]):
            self._validate_and_review(credit_note, '')

    @skip_unless_external
    def test_03_debit_note_standalone(self):
        ''' Test the success of issuing a debit note without an original invoice linked'''
        debit_note = self.env['account.move'].create({
            'company_id': self.company_ri.id,
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'l10n_latam_document_type_id': self.document_type['debit_note_a'].id,
            'journal_id': self.journal.id,
            'l10n_ar_afip_asoc_period_start': date(2025, 10, 1),
            'l10n_ar_afip_asoc_period_end': date(2025, 10, 31),
            'line_ids': [Command.create({'product_id': self.product_iva_21.id, 'quantity': 1})]
        })
        expected_document = self.document_type['debit_note_a']
        self.assertEqual(debit_note.l10n_latam_document_type_id.display_name, expected_document.display_name, 'The document should be %s' % expected_document.display_name)
        with self.patch_client([('FECAESolicitar', 'FECAESolicitar-debit-note-request', 'FECAESolicitar-debit-note-response')]):
            self._validate_and_review(debit_note, '')
