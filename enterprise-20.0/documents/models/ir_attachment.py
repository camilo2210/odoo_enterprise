import io
import logging
from collections import defaultdict

from odoo import models, api, fields
from odoo.fields import Domain
from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter
from odoo.addons.mail.tools.discuss import Store

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    document_ids = fields.One2many('documents.document', 'attachment_id', export_string_translation=False)
    linked_document_id = fields.Many2one('documents.document', compute='_compute_linked_document_id')

    @api.depends_context('uid')
    @api.depends('document_ids', 'res_model', 'res_id')
    def _compute_linked_document_id(self):
        self.linked_document_id = False
        with_document_ids = self.filtered('document_ids')
        for attachment in with_document_ids:
            attachment.linked_document_id = attachment.document_ids[0]
        without_document_ids = (self - with_document_ids)._exclude_documents_mixin()
        if not without_document_ids:
            return
        checksums = without_document_ids.filtered('checksum').mapped('checksum')
        attachment_ids = self.env["ir.attachment"].sudo().search(Domain('checksum', 'in', checksums)).ids
        checksum_document_dict = dict(self.env['documents.document']._read_group(
            Domain.AND([
                Domain('attachment_id', 'in', attachment_ids),
                Domain('res_model', '=', False),
                Domain('res_id', '=', False),
            ]), groupby=['checksum'], aggregates=['id:recordset']))
        for attachment in without_document_ids:
            documents = checksum_document_dict.get(attachment.checksum)
            attachment.linked_document_id = documents and max(documents, key=lambda d: d.owner_id == self.env.user)

    def _exclude_documents_mixin(self):
        mixin_candidate_attachment_ids = set()
        for res_model, attachments in self.grouped('res_model').items():
            if not res_model or not issubclass(self.pool[res_model], self.pool['documents.mixin']):
                continue
            records_per_id = self.env[res_model].browse(set(attachments.mapped('res_id'))).grouped('id')
            for res_id, record_attachments in attachments.grouped('res_id').items():
                record = records_per_id[res_id]
                # The eligibility check may rely on related records the attachment reader cannot access.
                # Sudo only this classification, the linked document search still uses the reader's rights.
                if record.sudo()._check_create_documents():
                    for attachment in record_attachments:
                        mixin_candidate_attachment_ids.add(attachment.id)

        return self.filtered(lambda a: a.id not in mixin_candidate_attachment_ids)

    def _store_attachment_fields(self, res: Store.FieldList, **kwargs):
        super()._store_attachment_fields(res, **kwargs)
        if kwargs.get('chatter_fields'):
            res.one('linked_document_id', '_store_document_fields')

    def get_documents_operation_add_destination(self):
        self.ensure_one()
        return {'destination': 'MY', 'display_name': self.env._('My Drive')}

    @api.model
    def _pdf_split(self, new_files=None, open_files=None):
        """Creates and returns new pdf attachments based on existing data.

        :param new_files: the array that represents the new pdf
            structure::

                [{
                    'name': 'New File Name',
                    'new_pages': [{
                        'old_file_index': 7,
                        'old_page_number': 5,
                    }],
                }]
        :param open_files: array of open file objects.
        :returns: the new PDF attachments
        """
        vals_list = []
        pdf_from_files = [OdooPdfFileReader(open_file, strict=False) for open_file in open_files]
        
        for new_file in new_files:
            output = OdooPdfFileWriter()
            used_pages_by_pdf = defaultdict(set)
            for page in new_file['new_pages']:
                file_index = int(page['old_file_index'])
                page_index = page['old_page_number'] - 1
                input_pdf = pdf_from_files[file_index]
                output.add_page(input_pdf.pages[page_index])
                used_pages_by_pdf[file_index].add(page_index)
                if len(used_pages_by_pdf[file_index]) != len(input_pdf.pages):
                    continue
                try:
                    for fname, fcontent in input_pdf.get_attachments():
                        output.add_attachment(name=fname, data=fcontent)
                except Exception:  # noqa: BLE001
                    _logger.warning(
                        'Impossible to add (all) attachments from pdf at index %i',
                        file_index, exc_info=True,
                    )
            with io.BytesIO() as stream:
                output.write(stream)
                vals_list.append({
                    'name': new_file['name'] + ".pdf",
                    'raw': stream.getvalue(),
                })
        return self.create(vals_list)

    def create_document(self):
        self.ensure_one()
        record = (model := self.env.get(self.res_model)) is not None and model.browse(self.res_id)
        if record:
            record.check_access('read')
        is_mixin_user = isinstance(record, self.pool['documents.mixin'])
        if record and is_mixin_user and record._check_create_documents() and self.has_access('write'):
            self.sudo()._create_document({'res_model': self.res_model, 'res_id': self.res_id})
            return Store().add(self, '_store_attachment_fields', fields_params={"chatter_fields": True})
        defaults = self.get_documents_operation_add_destination()
        msg_body = ""
        if record and not is_mixin_user:
            msg_body = self.env._(
                "This document belongs to %(rec)s.",
                rec=record.sudo()._get_html_link(title=record.display_name),
            )
        attachment_copy = self.copy({'res_model': False, 'res_id': False})
        self.env['documents.document'].with_context(document_creation_note=msg_body).create({
            'attachment_id': attachment_copy.id,
            'type': attachment_copy.type,
            'user_folder_id': defaults['destination'],
        })
        return Store().add(self, '_store_attachment_fields', fields_params={"chatter_fields": True})

    def _create_document(self, vals):
        """
        Implemented by bridge modules that create new documents if attachments are linked to
        their business models.

        :param vals: the create/write dictionary of ir attachment
        :return: True if new documents are created
        """
        # Special case for documents
        if vals.get('res_model') == 'documents.document' and vals.get('res_id'):
            document = self.env['documents.document'].search_fetch(
                [('id', '=', vals['res_id'])], [])
            if document.type == 'request':
                document.attachment_id = self[0].id
            return False

        # Generic case for all other models
        res_model = vals.get('res_model')
        res_id = vals.get('res_id')
        model = self.env.get(res_model)
        if model is not None and res_id and issubclass(self.pool[res_model], self.pool['documents.mixin']):
            vals_list = [
                model.browse(res_id)._get_document_vals(attachment)
                for attachment in self
                if not attachment.res_field and model.browse(res_id)._check_create_documents()
            ]
            vals_list = [vals for vals in vals_list if vals]  # Remove empty values
            self.env['documents.document'].create(vals_list)
            return True
        return False

    def copy(self, default=None):
        return super(IrAttachment, self.with_context(no_document=True)).copy(default)

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        for attachment, vals in zip(attachments, vals_list):
            # the context can indicate that this new attachment is created from documents, and therefore
            # doesn't need a new document to contain it.
            if not self.env.context.get('no_document') and not attachment.res_field:
                attachment.sudo()._create_document(dict(vals, res_model=attachment.res_model, res_id=attachment.res_id))
        return attachments

    def write(self, vals):
        old_values = {
            att.id: (att.res_model, att.res_id)
            for att in self
        } if 'res_model' in vals or 'res_id' in vals else {}
        res = super().write(vals)
        for attachment in self:
            if (
                old_values and old_values.get(attachment.id) != (attachment.res_model, attachment.res_id)
                and not self.env.context.get('no_document') and not attachment.res_field
            ):
                attachment.sudo()._create_document(dict(res_model=attachment.res_model, res_id=attachment.res_id))
        return res

    @api.ondelete(at_uninstall=False)
    def unlink_archive_document(self):
        """Send linked document to the trash with a copy of the attachment."""
        if not self:
            return
        attachment_candidates = self.filtered(  # filter only on other document types valid attachments
            lambda a: a.res_id and a.res_model not in (False, "mail.compose.message"))
        documents_sudo = attachment_candidates.sudo().with_context(active_test=False).document_ids
        if not documents_sudo:
            return
        attachments_to_copy_sudo = documents_sudo.attachment_id.with_context(no_document=True)
        copied_attachments_ids = attachments_to_copy_sudo.copy(default={'res_model': False, 'res_id': 0}).ids
        linked_attachments_sudo = attachments_to_copy_sudo.filtered(lambda a: a.res_model != 'documents.document')
        existing_parents = {
            res_model: {*self.env[res_model].sudo().browse(set(attachments.mapped('res_id'))).exists().ids}
            for res_model, attachments in linked_attachments_sudo.grouped('res_model').items()
        }
        documents_to_reset_sudo = documents_sudo.filtered(
            lambda d: d.attachment_id.res_model in existing_parents
                      and d.attachment_id.res_id not in existing_parents[d.attachment_id.res_model])
        # Disconnect from deleted records because the document write method reads the related record.
        documents_to_reset_sudo.write({'res_model': False, 'res_id': False})
        documents_sudo_not_already_archived = documents_sudo.filtered(lambda d: d.active)
        for doc_sudo, attachment_id in zip(documents_sudo, copied_attachments_ids):
            doc_sudo.write({
                'active': False,
                'attachment_id': attachment_id,
                'res_model': doc_sudo.res_model,
                'res_id': doc_sudo.res_id,
            })
        # TDE note: use with_source
        documents_sudo_not_already_archived._message_log_batch({
            doc.id: self.env['ir.qweb']._render(
                'documents.tracking_auto_archive_by_dependency', {}, minimal_qcontext=True)
            for doc in documents_sudo})
