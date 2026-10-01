# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Domain


class HrJob(models.Model):
    _name = 'hr.job'
    _inherit = ['hr.job', 'documents.mixin']

    documents_bridge_enabled = fields.Boolean(related='company_id.documents_recruitment_settings')

    def _compute_document_count(self):
        doc_by_record = self.env['documents.document']._read_group(
            self._get_documents_domain(),
            groupby=['res_model', 'res_id'],
            aggregates=['__count'],
        )
        doc_by_record = {(res_model, res_id): count for res_model, res_id, count in doc_by_record}
        for job in self:
            job.document_count = (
                doc_by_record.get(('hr.job', job.id), 0)
                + sum(doc_by_record.get(('hr.applicant', a.id), 0) for a in job.application_ids)
            )

    def _get_document_folder(self):
        return self.company_id.recruitment_folder_id

    def _check_create_documents(self):
        return self.company_id.documents_recruitment_settings and super()._check_create_documents()

    def _get_documents_domain(self):
        return super()._get_documents_domain() | Domain(
            [('type', '!=', 'folder'), ('res_model', '=', 'hr.applicant'), ('res_id', 'in', self.application_ids.ids)]
        )

    def action_open_attachments(self):
        if not self.company_id.documents_recruitment_settings:
            return super().action_open_attachments()
        return self.action_open_documents()
