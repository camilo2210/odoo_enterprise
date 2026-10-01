from odoo.tests import Form, tagged
from .common import TestDoEdiCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEdiSequence(TestDoEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_doc_types_sequences(self):
        """ Tests that all document types sequence is formatted properly"""
        type_31_move = self._create_invoice(doc_type=self.doc_type_31)
        type_31_move.action_post()
        self.assertEqual(type_31_move.name, 'E310000000001')

        type_32_move = self._create_invoice(doc_type=self.doc_type_32)
        type_32_move.action_post()
        self.assertEqual(type_32_move.name, 'E320000000001')

        # Debit note
        type_33_move = self._create_invoice(
            doc_type=self.doc_type_33,
            move_type='out_invoice',
            reversed_entry_id=type_31_move.id,
            l10n_do_edi_modification_code='1',
        )
        type_33_move.action_post()
        self.assertEqual(type_33_move.name, 'E330000000001')

        # Credit note
        type_34_move = self._create_invoice(
            doc_type=self.doc_type_34,
            move_type='out_refund',
            debit_origin_id=type_32_move.id,
            l10n_do_edi_modification_code='1',
        )
        type_34_move.action_post()
        self.assertEqual(type_34_move.name, 'E340000000001')

    def test_sequence_shared_across_journals(self):
        """ Tests for sequence numbering is shared across journals for the same document type."""
        default_journal_move = self._create_invoice(journal_id=self.journal_sale.id)
        default_journal_move.action_post()
        self.assertEqual(default_journal_move.name, 'E310000000001')

        # Create a new journal and move
        journal_2 = self.journal_sale.copy({'code': 'INV2', 'name': 'Sale Journal 2'})
        journal_2_move = self._create_invoice(journal_id=journal_2.id)
        journal_2_move.action_post()
        self.assertEqual(journal_2_move.name, 'E310000000002')

    def test_sequence_with_modified_start_number(self):
        """ Test that the sequence changes according to the modified start number with existing invoices"""
        # Create an invoice with the default start number of the range
        move_1 = self._create_invoice()
        move_1.action_post()
        self.assertEqual(move_1.name, 'E310000000001')

        # Clear the sequence cache to use the new modified start number
        self.env['account.move']._get_sequence_cache().clear()

        # Change the start number of the range
        self.range_31.start_number = 500
        self.doc_type_31.with_company(move_1.company_id.id).l10n_do_edi_property_document_range_id = self.range_31

        # Create another invoice after the change
        move_500 = self._create_invoice()
        move_500.action_post()
        self.assertEqual(move_500.name, 'E310000000500')

    def test_compute_document_number_from_name(self):
        """ Tests that the document number is dropping the prefix properly"""
        move = self._create_invoice()
        move.action_post()
        self.assertEqual(move.name, 'E310000000001')
        self.assertEqual(move.l10n_latam_document_number, '0000000001')

    def test_inverse_document_number_sets_name(self):
        """ Tests that the sequence is formatted properly from the document number"""
        move = self._create_invoice()
        move.l10n_latam_document_number = '0000000042'
        self.assertEqual(move.name, 'E310000000042')

    def test_document_sequence_onchange_partner(self):
        """ Tests that the document sequence is in proper format upon partner changes"""
        move = self._create_invoice()
        move.action_post()
        move.button_draft()
        with Form(move) as move_form:
            move_form.partner_id = self.no_vat_partner
        self.assertEqual(move.name, 'E310000000001')

    def test_sequence_not_shared_between_sale_and_purchase_journals(self):
        """ Tests that activating 'Use Documents' on both a Sale and a Purchase journal with the same
        document type affect the sequence number only of customer invoices and not bills."""

        self.journal_purchase.l10n_latam_use_documents = True
        vendor_bill = self._create_invoice(
            move_type='in_invoice',
            journal_id=self.journal_purchase.id,
            doc_type=self.doc_type_31,
        )
        vendor_bill.l10n_latam_document_number = '0000056'
        vendor_bill.action_post()
        self.assertEqual(vendor_bill.name, 'E310000056')

        customer_invoice = self._create_invoice(doc_type=self.doc_type_31)
        customer_invoice.action_post()
        self.assertEqual(customer_invoice.name, 'E310000000001')
