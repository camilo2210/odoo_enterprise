from odoo import models, _
from odoo.exceptions import UserError


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    def document_hr_recruitment_create_hr_applicant(self):
        if self.filtered(lambda doc: doc.type != 'binary' or doc.shortcut_document_id):
            raise UserError(_("This action can only be applied on documents."))
        applicants = self.env['hr.applicant']
        for document in self:
            applicant = self.env['hr.applicant'].create({
                'partner_name': "New Applicant from Documents",
                'recruiter_id': False,
            })
            applicants |= applicant
            this_document = document
            if document.res_model or document.res_id:
                this_document = document.copy()
                attachment_id_copy = document.attachment_id.with_context(no_document=True).copy()
                this_document.write({'attachment_id': attachment_id_copy.id})

            this_document.attachment_id.with_context(no_document=True).write({
                'res_model': 'hr.applicant',
                'res_id': applicant.id
            })
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.applicant',
            'name': 'Applicant',
            'view_mode': 'list,form',
            'views': [(False, "list"), (False, "form")],
            'domain': [('id', 'in', applicants.ids)],
            'context': self.env.context,
        }
        if len(applicants) == 1:
            action.update(
                view_mode='form',
                views=[(False, "form")],
                res_id=applicants[0].id,
            )
        return action
