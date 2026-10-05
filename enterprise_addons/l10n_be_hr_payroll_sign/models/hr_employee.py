from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox
import io

from odoo import models, Command


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_report_employment_certificate(self):
        attachment = super().action_report_employment_certificate()

        # The report engine can be configured to only render the document as HTML
        # (e.g. no PDF engine available on the system like runbot tests).
        # In that case, the signature flow cannot be set up on a non-PDF document
        if not attachment.raw.content.startswith(b'%PDF'):
            return attachment

        template_id, _name = self.env['sign.template'].create_sign_template_from_ir_attachment_data(
            attachment_id=attachment.id,
            res_id=self.id,
            res_model=self._name,
        )

        document = self.env['sign.template'].browse(template_id).document_ids[:1]
        item_type = self.env['sign.item.type'].search([('item_type', '=', 'signature')], limit=1)
        role = self.env.ref('sign.sign_item_role_default')

        ANCHOR_TEXT = '__SIGN_HERE__'
        for page in list(extract_pages(io.BytesIO(attachment.raw))):
            page_height = page.height
            for element in page:
                if isinstance(element, LTTextBox) and ANCHOR_TEXT in element.get_text():
                    posY = 1.0 - ((element.y0 - 5) / page_height)
                    posY = max(0.0, min(posY, 0.95))

                    self.env['sign.item'].create({
                        'document_id': document.id,
                        'type_id': item_type.id,
                        'responsible_id': role.id,
                        'required': True,
                        'page': 1,
                        'posX': 0.65,
                        'posY': posY,
                        'width': item_type.default_width,
                        'height': item_type.default_height,
                        'name': 'Sign here',
                    })

                    if self.env.context.get('cron_id'):
                        responsible = self.current_version_id.hr_responsible_id or self.env.user
                    else:
                        responsible = self.env.user

                    sign_request = self.env['sign.request'].create({
                        'template_id': template_id,
                        'reference': f'Employment Certificate - {self.name}',
                        'request_item_ids': [Command.create({
                            'partner_id': responsible.partner_id.id,
                            'role_id': role.id,
                        })],
                    })
                    return sign_request.go_to_document()
        return attachment
