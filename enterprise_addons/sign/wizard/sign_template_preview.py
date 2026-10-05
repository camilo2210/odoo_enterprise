# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import BinaryBytes
from odoo.tools.pdf import PdfFileReader
from odoo.tools.pdf.signature import IncrementalPdfMerge


class SignTemplatePreview(models.TransientModel):
    _name = 'sign.template.preview'
    _description = 'Sign Tempate Preview'

    template_id = fields.Many2one('sign.template', ondelete='cascade')
    document_id = fields.Many2one('sign.document', ondelete='cascade')
    pdf_data = fields.Binary(compute='_compute_pdf')

    @api.depends('template_id')
    def _compute_pdf(self):
        for wiz in self:
            if not wiz.template_id:
                continue
            wiz.template_id.check_access('read')
            overlay_pdf_raw, overlay_regions = wiz.document_id.render_document_with_items()
            incremental_pdf_merger = IncrementalPdfMerge(bytes(wiz.document_id.attachment_id.raw))
            incremental_pdf_merger.merge_pdf_regions_as_annotations(
                PdfFileReader(overlay_pdf_raw, strict=False), overlay_regions, "sign_items_preview")
            wiz.pdf_data = BinaryBytes(incremental_pdf_merger.get_output_stream_value())
