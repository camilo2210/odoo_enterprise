import io
import uuid
import datetime
from contextlib import suppress

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from odoo.tools.image import ImageProcess
from odoo.tools.pdf import PdfFileReader
from odoo.tools.pdf.signature import (
    IncrementalPdfMerge,
    PdfSigner,
    certificate_common_name,
    next_signature_appearance_origin,
)


class SignRequestDocument(models.Model):
    _name = 'sign.request.document'
    _description = "Sign Request Document"

    sign_request_id = fields.Many2one('sign.request', string="Sign Request", required=True, index=True, ondelete='restrict')
    file = fields.Binary(readonly=True, string="Document File", attachment=True, copy=False)
    document_id = fields.Many2one('sign.document', string="Document", required=True, index=True, ondelete='restrict')
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('awaiting_signature', 'Awaiting Signature'),
        ('completed', 'Completed'),
    ], default='in_progress', required=True, copy=False, index=True)
    applied_item_ids = fields.Many2many(
        'sign.request.item', 'sign_request_document_applied_items_rel',
        string="Applied Signers", copy=False,
        help="Signers whose values are already stamped on the file.")
    frozen_file = fields.Binary(readonly=True, attachment=True, copy=False,
        help="Bytes an external signature is being computed over, kept until it comes back.")

    _request_document_uniq = models.Constraint(
        'unique (sign_request_id, document_id)',
        "A document can only have one working copy per sign request.",
    )

    def _get_file_bytes(self):
        """ Current working bytes, starting from the original document before any signer. """
        self.ensure_one()
        return bytes(self.file) if self.file else bytes(self.document_id.attachment_id.raw)

    def _apply_completed_items(self):
        """ Stamps the values of every completed signer not yet on the file, as a single
        incremental update.

        Runs before every signature event so each signature covers all values it should.
        """
        for document in self:
            if document.state != 'in_progress':
                continue  # if the signature is in flight, or already sealed
            unapplied_items = document.sign_request_id.request_item_ids.filtered(
                lambda item: item.state == 'completed') - document.applied_item_ids
            if unapplied_items:
                stamped_raw = document._stamp_items_values(unapplied_items, document._get_file_bytes())
                if stamped_raw:
                    document.file = BinaryBytes(stamped_raw)
                document.applied_item_ids += unapplied_items

    def _stamp_items_values(self, request_items, pdf_raw):
        """ Returns ``pdf_raw`` extended with one incremental update merging the given
        signers' field values, or None when they have no value on this document.
        """
        self.ensure_one()
        sign_item_ids = [item.id for items in self.document_id._get_sign_items_by_page().values() for item in items]
        values_dict = self.env['sign.request.item.value']._read_group(
            [('sign_item_id', 'in', sign_item_ids), ('sign_request_item_id', 'in', request_items.ids)],
            groupby=['sign_item_id'],
            aggregates=['value:array_agg', 'frame_value:array_agg', 'frame_has_hash:array_agg']
        )
        if not values_dict:
            return None  # signers have no value on this document
        signed_values = {
            sign_item.id: {
                'value': values[0],
                'frame': frame_values[0],
                'frame_has_hash': frame_has_hashes[0],
            }
            for sign_item, values, frame_values, frame_has_hashes in values_dict
        }

        overlay_pdf_raw, overlay_regions = self.document_id.render_document_with_items(
            signed_values=signed_values, values_dict=values_dict)
        overlay_pdf = PdfFileReader(overlay_pdf_raw, strict=False)
        incremental_pdf_merger = IncrementalPdfMerge(pdf_raw)
        incremental_pdf_merger.merge_pdf_regions_as_annotations(
            overlay_pdf, overlay_regions, f"sign_values_{uuid.uuid4().hex[:6]}")
        return incremental_pdf_merger.get_output_stream_value()

    @staticmethod
    def _get_company_seal_logo(company):
        """The company's seal logo, or ``None`` if there is nothing to draw (e.g., the
        default Odoo logo or an unsupported format such as SVG)."""
        if company.uses_default_logo or not company.logo_web:
            return None
        with suppress(UserError):
            logo = ImageProcess(company.logo_web.content)
            return io.BytesIO(logo.image_quality()) if logo.image else None
        return None

    def _freeze_for_external_signature(self, request_item):
        """ Freezes the bytes an external signer is about to sign.

        Flushes the completed values first so the signature covers them, then adds the
        signer's own values. Those become durable only when the signature comes back.

        :param request_item: The signer performing the external signature.
        :return: The frozen bytes, to be sent to the signing service.
        """
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(self.env._("Another signature is currently in progress, or this document has already been fully signed."))
        self._apply_completed_items()

        frozen_raw = self._get_file_bytes()
        if request_item not in self.applied_item_ids:
            frozen_raw = self._stamp_items_values(request_item, frozen_raw) or frozen_raw
        self.write({'frozen_file': BinaryBytes(frozen_raw), 'state': 'awaiting_signature'})
        return frozen_raw

    def _finalize_external_signature(self, request_item, signature_increment):
        """ Appends the signing service's increment to the frozen file.

        :param request_item: The signer whose signature came back.
        :param signature_increment: The PDF increment holding the signature, as returned
            by the signing service for the frozen bytes.
        :return: True when applied, False when nothing was frozen.
        """
        self.ensure_one()
        if self.state != 'awaiting_signature':
            return False

        self.write({
            'file': BinaryBytes(bytes(self.frozen_file) + signature_increment),
            'frozen_file': False,
            'state': 'in_progress',
        })
        self.applied_item_ids += request_item
        return True

    def _discard_pending_signature(self):
        """ Drops the frozen file so signing can restart from the last durable file. """
        documents = self.filtered(lambda document: document.state == 'awaiting_signature')
        documents.write({'frozen_file': False, 'state': 'in_progress'})

    def _finalize_documents(self):
        """ Applies the remaining signers, stamps the log hash and seals
        the file with the company signature if available. """
        self._apply_completed_items()
        for document in self.filtered(lambda document: document.state == 'in_progress'):
            sign_request = document.sign_request_id
            file_raw = document._get_file_bytes()

            company = sign_request.communication_company_id
            certificate = company.signing_certificate_id if 'signing_certificate_id' in company._fields else None
            will_seal = bool(certificate and certificate.pem_certificate)

            # a document the signers cryptographically signed should not get an unsigned
            # incremental change afterwards: only stamp the log hash when a company seal protects it
            requires_external_signature = any(
                sign_request.request_item_ids.role_id.mapped('requires_external_signature'))
            final_log_hash = sign_request._get_final_signature_log_hash()
            stamped_raw = file_raw
            if final_log_hash and not (requires_external_signature and not will_seal):
                overlay_pdf_raw, overlay_regions = document.document_id._render_log_hash_overlay(final_log_hash)
                overlay_pdf = PdfFileReader(overlay_pdf_raw, strict=False)
                incremental_pdf_merger = IncrementalPdfMerge(file_raw)
                incremental_pdf_merger.merge_pdf_regions_as_annotations(
                    overlay_pdf, overlay_regions, annotations_title="final_signature_hash")
                stamped_raw = incremental_pdf_merger.get_output_stream_value()

            if will_seal:
                signing_time = datetime.datetime.now(datetime.timezone.utc)
                unique_field_name = f"{sign_request._get_signing_field_name()}_{uuid.uuid4().hex[:6]}"

                common_name = certificate_common_name(certificate.pem_certificate.content) if will_seal else None
                appearance = document.document_id.render_certificate_signature_widget(
                    common_name, signing_time, logo_image=self._get_company_seal_logo(company))
                appearance_pdf = PdfFileReader(appearance, strict=False) if appearance else None
                origin = next_signature_appearance_origin(stamped_raw, appearance_pdf) if appearance_pdf else None

                signer = PdfSigner(stamped_raw, company, signing_time)
                signed_output = signer.sign_pdf(appearance_pdf, unique_field_name, origin)
            else:
                signed_output = None

            document.file = BinaryBytes(signed_output or (file_raw if requires_external_signature else stamped_raw))
            document.state = 'completed'
