# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
from types import SimpleNamespace

from PIL import Image

from odoo import Command
from odoo.addons.sign.tests.sign_request_common import SignRequestCommon
from odoo.tools import BinaryBytes
from odoo.tools.pdf import PdfFileReader
from odoo.tools.pdf.signature import get_page_media_box


class TestSignRequestDocument(SignRequestCommon):

    def get_page_annotation_rects(self, page):
        return [tuple(float(coordinate) for coordinate in annotation.get_object()['/Rect'])
                for annotation in (page.get('/Annots') or [])]

    def create_sign_request_as_sender(self, sender):
        """ A request sent by a plain sign user, so its flow runs with the sender's rights. """
        self.template_2_roles.authorized_ids += sender
        return self.env['sign.request'].with_user(sender).create({
            'template_id': self.template_2_roles.id,
            'reference': self.template_2_roles.display_name,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_2.id,
                'role_id': self.role_signer_1.id,
            }), Command.create({
                'partner_id': self.partner_3.id,
                'role_id': self.role_signer_2.id,
            })],
        })

    def sign_all(self, sign_request):
        role_to_item = {item.role_id: item for item in sign_request.request_item_ids}
        values_by_role = {
            self.role_signer_1: self.signer_1_sign_values,
            self.role_signer_2: self.signer_2_sign_values,
            self.role_signer_3: self.signer_3_sign_values,
        }
        for role, item in role_to_item.items():
            item.sign(values_by_role[role])

    def test_full_flow_creates_completed_documents(self):
        sign_request = self.create_sign_request_3_roles(
            signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
        original_raw = bytes(sign_request.template_id.document_ids.attachment_id.raw)

        self.sign_all(sign_request)

        self.assertEqual(sign_request.state, 'signed')
        documents = sign_request.request_document_ids
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents.state, 'completed')
        self.assertEqual(documents.applied_item_ids, sign_request.request_item_ids)

        # Incremental updates only append, the original bytes shouldn't be touched
        final_raw = bytes(documents.file)
        self.assertEqual(final_raw[:len(original_raw)], original_raw)

        self.assertTrue(sign_request.completed_document_attachment_ids)

    def test_completed_document_annotations_never_overlap(self):
        """ Every value is shown through an annotation of its own, tight enough to leave the
        rest of the page visible. Overlapping ones would read as hidden content to validators. """
        sign_request = self.create_sign_request_3_roles(
            signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
        sign_request.certificate_reference = True  # stamps the log hash too, one more annotation

        self.sign_all(sign_request)

        document = sign_request.request_document_ids
        reader = PdfFileReader(io.BytesIO(bytes(document.file)), strict=False)
        # one annotation per sign item of the page, plus the one of the log hash reference
        self.assertEqual(
            len(self.get_page_annotation_rects(reader.pages[0])),
            len(document.document_id.sign_item_ids) + 1)

        for page in reader.pages:
            page_box = get_page_media_box(page)
            rects = self.get_page_annotation_rects(page)
            for index, rect in enumerate(rects):
                self.assertTrue(
                    float(page_box.left) <= rect[0] < rect[2] <= float(page_box.right)
                    and float(page_box.bottom) <= rect[1] < rect[3] <= float(page_box.top),
                    f"the annotation {rect} is not a visible area of the page")
                for other in rects[index + 1:]:
                    self.assertFalse(
                        rect[0] < other[2] and other[0] < rect[2] and rect[1] < other[3] and other[1] < rect[3],
                        f"the annotations {rect} and {other} cover each other")

    def test_apply_completed_items_is_idempotent(self):
        sign_request = self.create_sign_request_3_roles(
            signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
        role_to_item = {item.role_id: item for item in sign_request.request_item_ids}
        role_to_item[self.role_signer_1].sign(self.signer_1_sign_values)
        role_to_item[self.role_signer_2].sign(self.signer_2_sign_values)

        documents = sign_request._get_signing_documents()
        documents._apply_completed_items()
        applied_once = bytes(documents.file)
        self.assertEqual(len(documents.applied_item_ids), 2)

        documents._apply_completed_items()
        self.assertEqual(bytes(documents.file), applied_once, "a second run must not touch the file")

        role_to_item[self.role_signer_3].sign(self.signer_3_sign_values)
        self.assertEqual(documents.state, 'completed')
        self.assertEqual(len(documents.applied_item_ids), 3)

    def test_apply_completed_items_only_touches_writable_files(self):
        sign_request = self.create_sign_request_1_role(signer=self.partner_1, cc_partners=self.partner_4)
        document = sign_request._get_signing_documents()
        document.state = 'awaiting_signature'

        sign_request.request_item_ids.sign(self.single_signer_sign_values)

        self.assertFalse(document.applied_item_ids, "an awaiting signing file must not be stamped")
        # once writable again, the finalize catches up
        document.state = 'in_progress'
        document._finalize_documents()
        self.assertEqual(document.state, 'completed')
        self.assertEqual(document.applied_item_ids, sign_request.request_item_ids)

    def test_cancel_unlinks_working_documents(self):
        sign_request = self.create_sign_request_2_roles(
            signer_1=self.partner_1, signer_2=self.partner_2, cc_partners=self.partner_4)
        sign_request._get_signing_documents()
        self.assertTrue(sign_request.request_document_ids)

        sign_request.cancel()
        self.assertFalse(sign_request.request_document_ids)

    def test_sender_cancels_request_with_working_documents(self):
        sign_request = self.create_sign_request_as_sender(self.user_1)
        sign_request.sudo()._get_signing_documents()

        sign_request.cancel()

        self.assertFalse(sign_request.request_document_ids)

    def test_sender_deletes_request_with_working_documents(self):
        sign_request = self.create_sign_request_as_sender(self.user_1)
        documents = sign_request.sudo()._get_signing_documents()
        documents.file = BinaryBytes(b'%PDF-1.4 stamped values')
        files = self.env['ir.attachment'].search([
            ('res_model', '=', 'sign.request.document'), ('res_id', 'in', documents.ids), ('res_field', '=', 'file')])
        self.assertTrue(files)

        sign_request.unlink()

        self.assertFalse(documents.exists())
        self.assertFalse(files.exists(), "a deleted working document must not leave its file behind")

    def test_cancelling_a_request_removes_the_frozen_files(self):
        sign_request = self.create_sign_request_as_sender(self.user_1)
        document = sign_request.sudo()._get_signing_documents()[0]
        document._freeze_for_external_signature(sign_request.request_item_ids[0])
        frozen_file = self.env['ir.attachment'].search([
            ('res_model', '=', 'sign.request.document'), ('res_id', '=', document.id),
            ('res_field', '=', 'frozen_file')])
        self.assertTrue(frozen_file)

        sign_request.cancel()

        self.assertFalse(frozen_file.exists(), "a discarded freeze must not leave its file behind")

    def test_finalizing_the_same_signature_twice(self):
        sign_request = self.create_sign_request_1_role(signer=self.partner_1, cc_partners=self.partner_4)
        request_item = sign_request.request_item_ids
        request_item._fill(self.single_signer_sign_values)
        document = sign_request._get_signing_documents()

        document._freeze_for_external_signature(request_item)
        self.assertTrue(document._finalize_external_signature(request_item, b'%%signature%%'))
        signed_raw = bytes(document.file)

        # a late or duplicate delivery is ignored
        self.assertFalse(document._finalize_external_signature(request_item, b'%%signature%%'))
        self.assertEqual(bytes(document.file), signed_raw)

    def test_discarding_a_freeze_lets_the_signer_start_again(self):
        sign_request = self.create_sign_request_1_role(signer=self.partner_1, cc_partners=self.partner_4)
        request_item = sign_request.request_item_ids
        request_item._fill(self.single_signer_sign_values)
        document = sign_request._get_signing_documents()
        durable_raw = document._get_file_bytes()

        document._freeze_for_external_signature(request_item)
        document._discard_pending_signature()

        self.assertEqual(document.state, 'in_progress')
        self.assertFalse(document.frozen_file)
        self.assertEqual(
            document._get_file_bytes(), durable_raw,
            "the values of an abandoned attempt never reached the durable file")
        self.assertFalse(document.applied_item_ids)

        # a fresh attempt starts clean and completes
        document._freeze_for_external_signature(request_item)
        self.assertTrue(document._finalize_external_signature(request_item, b'%%signature%%'))
        self.assertIn(request_item, document.applied_item_ids)

    def test_signed_request_regenerates_documents_from_values(self):
        sign_request = self.create_sign_request_1_role(signer=self.partner_1, cc_partners=self.partner_4)
        sign_request.request_item_ids.sign(self.single_signer_sign_values)
        self.assertEqual(sign_request.state, 'signed')

        # Legacy/lazy path: no documents yet on an already signed request
        sign_request.request_document_ids.unlink()
        sign_request._generate_completed_documents()

        documents = sign_request._get_completed_documents()
        self.assertEqual(documents.state, 'completed')
        self.assertEqual(documents.applied_item_ids, sign_request.request_item_ids)

    def test_company_seal_logo(self):
        """ A logo the canvas cannot draw is dropped, never raised at a signer. """
        buffer = io.BytesIO()
        Image.new('RGB', (2, 2)).save(buffer, 'PNG')
        seal_logo = self.env['sign.request.document']._get_company_seal_logo

        def company(logo, uses_default_logo=False):
            return SimpleNamespace(uses_default_logo=uses_default_logo, logo_web=BinaryBytes(logo))

        self.assertTrue(seal_logo(company(buffer.getvalue())), "a raster logo brands the seal")
        self.assertIsNone(seal_logo(company(buffer.getvalue(), uses_default_logo=True)))
        self.assertIsNone(seal_logo(company(b'<svg xmlns="http://www.w3.org/2000/svg"/>')))
        self.assertIsNone(seal_logo(company(b'\x00 not an image at all')))
        self.assertIsNone(seal_logo(company(b'')))
