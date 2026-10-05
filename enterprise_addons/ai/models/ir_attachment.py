# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import contextlib
import io
import logging

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.http.router import root
from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter, to_pdf_stream, PdfReadError
from odoo.tools.image import ImageProcess

from odoo.addons.mail.tools.discuss import Store
from odoo.addons.ai.utils.ai_image_tools import retrieve_image_data_from_record, field_to_image_path, closest_aspect_ratio, AI_SUPPORTED_IMG_TYPES
from odoo.addons.ai.utils.ai_text_tools import process_csv_text


_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _name = "ir.attachment"
    _inherit = ['ir.attachment', 'ai.embedding.mixin']

    ai_sources_ids = fields.One2many("ai.agent.source", "attachment_id", string="AI Agent Sources")

    TABULAR_FILE_TYPES = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # xlsx
        'application/vnd.ms-excel',  # xls
        'application/vnd.oasis.opendocument.spreadsheet',  # ods
        'text/csv',  # csv
    ]

    def _get_attachment_content(self):
        """
        Get the indexing-processed content of the attachment
        """
        self.ensure_one()
        attachment_content = ''
        if self.mimetype in self.TABULAR_FILE_TYPES:
            sheets = self.index_content.split('\n\n')
            for sheet in sheets:
                if sheet:
                    rows_list = process_csv_text(sheet)
                    if rows_list:
                        result = '\n'.join(str(row) for row in rows_list)
                        attachment_content += result + '\n'
        else:
            attachment_content = self.index_content

        if not attachment_content:
            return None

        # Check for reasonable content length
        if len(attachment_content.strip()) <= 10:
            return None

        return attachment_content

    def _get_field_attachments(self, records, fnames):
        """Return the attachments backing the ``fnames`` binary fields of ``records``."""
        if not (records.ids and fnames):
            return self.browse()
        return self.search([
            ('res_model', '=', records._name),
            ('res_field', 'in', fnames),
            ('res_id', 'in', records.ids),
        ])

    def _ai_read(self, fnames=None, files_parts=None, files_checksums=None):
        """When attachments are inserted in a prompt, one send the files (or indexed contents) to
        the LLMs.
        """
        max_pdf_pages = self.env.context.get("ai_max_pdf_pages")
        if fnames:
            return super()._ai_read(fnames, files_parts, files_checksums)

        if files_parts is None:
            files_parts = []
        if files_checksums is None:
            files_checksums = set()
        vals = []
        for attachment in self:
            if attachment.checksum in files_checksums:
                vals.append({'id': attachment.id, 'file': f"<file_{attachment.checksum}/>"})
                continue
            extension = attachment.mimetype.split('/')[-1]
            if extension == 'pdf' and not attachment.url:
                # Extract the X first / last pages of the PDFs
                reader = None
                with contextlib.suppress(PdfReadError):
                    reader = OdooPdfFileReader(to_pdf_stream(attachment), strict=False)
                if not reader or not max_pdf_pages or len(reader.pages) <= max_pdf_pages:
                    b64_datas = attachment.raw.to_base64()
                else:
                    writer = OdooPdfFileWriter()
                    start_pages = max_pdf_pages // 2
                    end_pages = max_pdf_pages - start_pages
                    for p in (*range(start_pages), *range(len(reader.pages) - end_pages, len(reader.pages))):
                        writer.add_page(reader.pages[p])
                    out_buff = io.BytesIO()
                    writer.write(out_buff)
                    b64_datas = base64.b64encode(out_buff.getvalue()).decode()

                files_checksums.add(attachment.checksum)
                files_parts.append({
                    'type': 'inline_data',
                    'mimetype': 'application/pdf',
                    'data': b64_datas,

                })
            elif extension in AI_SUPPORTED_IMG_TYPES:
                raw_data = retrieve_image_data_from_record(attachment, 'raw')['content']
                aspect_ratio = '1:1'
                size = None
                try:
                    image_process = ImageProcess(raw_data)
                    size = image_process.image.size
                    if max(size) > 1024:
                        raw_data = image_process \
                            .crop_resize(min(size[0], 1024), min(size[1], 1024), 0, 0) \
                            .image_quality(output_format='PNG')
                except Exception as e:  # noqa: BLE001
                    _logger.error("Image resize failed %s", e)
                finally:
                    if size:
                        aspect_ratio = closest_aspect_ratio(width=size[0], height=size[1])
                if (
                    attachment.res_field and attachment.res_model in self.env and attachment.res_id
                    and (image_record := self.env[attachment.res_model].browse(attachment.res_id).exists())
                ):
                    image_path = field_to_image_path(image_record, attachment.res_field)
                else:
                    image_path = field_to_image_path(attachment, 'raw')
                files_checksums.add(attachment.checksum)
                files_parts.append({
                    'type': 'inline_data',
                    'mimetype': attachment.mimetype,
                    'data': base64.b64encode(raw_data).decode(),
                    'metadata': {
                        'image_path': image_path,
                        'aspect_ratio': aspect_ratio
                    }
                })
            else:
                if not attachment.index_content or attachment.index_content == "application":
                    files_checksums.add(attachment.checksum)
                    files_parts.append({
                        'type': 'text',
                        'text': f"File '{attachment.name}' ({attachment.mimetype}): Filetype not supported",
                    })
                    continue
                files_parts.append({
                    'type': 'text',
                    'text': f"Content of file '{attachment.name}' ({attachment.mimetype}): {attachment.index_content}",
                })
            vals.append({'id': attachment.id, 'file': f"<file_{attachment.checksum}/>"})
        return vals, files_parts, files_checksums

    def _retrieve_image_src_and_mimetype(self):
        self.ensure_one()
        result = {}
        if self.url:
            # When the URL targets a file located in an addon, assume it
            # is a path to the resource. It saves an indirection and
            # stream the file right away.
            static_path = root.get_static_file(
                self.url,
                host=self.env.context.get('HTTP_HOST', '')
            )
            if static_path:
                result['path'] = static_path
            else:
                result['url'] = self.url
        else:
            result['data'] = self.raw.content or b''
        result['mimetype'] = self.mimetype
        return result

    def _store_attachment_fields(self, res: Store.FieldList, **kwargs):
        super()._store_attachment_fields(res, **kwargs)
        media_fields = self._get_media_fields()
        for field in media_fields:
            res.attr(field)

    def _get_embedding_content(self):
        self.ensure_one()
        content = self._get_attachment_content()
        if not content:
            raise ValueError(self.env._("Failed to extract content from the attachment. Content must be at least 10 character long."))
        return content

    def _get_embedding_chunks(self):
        self.ensure_one()
        # If the attachment is a tabular file, return each row as a separate chunk
        if self.mimetype in self.TABULAR_FILE_TYPES:
            content = self._get_embedding_content()
            return content.strip().split('\n')
        return super()._get_embedding_chunks()

    def _get_duplicate_domain(self):
        self.ensure_one()
        return Domain("checksum", "=", self.checksum)

    @api.model
    def _get_records_to_embed_domain(self):
        return super()._get_records_to_embed_domain() & Domain("ai_sources_ids", "!=", False) & Domain("ai_sources_ids.status", "!=", "failed")

    def _get_embedding_models(self):
        self.ensure_one()
        return {source.agent_id.embedding_model for source in self.ai_sources_ids}

    def _on_embedding_failure(self, error):
        super()._on_embedding_failure(error)
        self.ai_sources_ids.write({
            "status": "skipped",
            "error_details": str(error),
        })
