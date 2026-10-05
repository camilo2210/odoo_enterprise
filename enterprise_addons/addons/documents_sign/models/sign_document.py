from odoo import api, models


class SignDocument(models.Model):
    _name = 'sign.document'
    _inherit = ['sign.document']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            attachment_id = vals.get('attachment_id')
            attachment = self.env['ir.attachment'].browse(attachment_id)

            if attachment:
                if attachment.res_model:
                    # Make a safe copy and explicitly set original_id for lineage tracking
                    vals['attachment_id'] = attachment.copy({
                        'original_id': attachment.id
                    }).id
                else:
                    # leave it unlinked
                    attachment.write({'res_model': False, 'res_id': 0})

        records = super().create(vals_list)

        for record in records:
            if record.attachment_id:
                record.attachment_id.write({
                    'res_model': record._name,
                    'res_id': record.id
                })

        return records
