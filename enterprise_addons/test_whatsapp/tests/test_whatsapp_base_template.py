from odoo import exceptions
from odoo.addons.whatsapp.tests.common import WhatsAppCommon
from odoo.tests import tagged, users


@tagged('wa_template')
class WhatsAppBaseTemplate(WhatsAppCommon):
    """Tests for WhatsApp base template field logic, including header type validation and computed resets."""

    @users('user_wa_admin')
    def test_template_header_attachment_mimetype(self):
        categ_types = [
            [
                'text/plain', 'application/pdf', 'application/vnd.ms-powerpoint', 'application/msword',
                'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ],  # document
            ['image/jpeg', 'image/png'],  # image
            ['video/mp4'],                # video
        ]
        all_types = [mimetype for categ in categ_types for mimetype in categ]
        dummy_data = self.image_attachment.raw
        for header_type, valid_types in zip(
            ['document', 'image', 'video'],
            categ_types,
        ):
            for mimetype in all_types:
                with self.subTest(header_type=header_type, mimetype=mimetype):
                    attachment = self.env['ir.attachment'].create({
                        'raw': dummy_data,
                        'mimetype': mimetype,
                        'name': f'Dummy {mimetype}',
                    })
                    tpl_vals = {
                        'body': f'Header {header_type} template',
                        'header_attachment_id': attachment.id,
                        'header_type': header_type,
                        'name': f'Header {header_type} {mimetype}',
                    }
                    if mimetype in valid_types:
                        self.env['whatsapp.test.base.template'].create(tpl_vals)
                    else:
                        with self.assertRaises(exceptions.ValidationError):
                            self.env['whatsapp.test.base.template'].create(tpl_vals)

    @users('user_wa_admin')
    def test_template_header_attachment_required(self):
        for header_type in ['document', 'image', 'video']:
            with self.subTest(header_type=header_type):
                tpl_vals = {
                    'body': f'Header {header_type} template with no attachment',
                    'header_type': header_type,
                    'name': f'Header {header_type} no attachment',
                }
                with self.assertRaises(exceptions.ValidationError):
                    self.env['whatsapp.test.base.template'].create(tpl_vals)

    @users('user_wa_admin')
    def test_template_header_field_reset_on_type_change(self):
        template = self.simple_whatsapp_template

        template.write({'header_type': 'document', 'header_attachment_id': self.document_attachment_wa_admin.id})
        self.assertEqual(template.header_attachment_id.res_model, template._name)
        self.assertEqual(template.header_attachment_id.res_id, template.id)

        template.write({'header_type': 'text', 'header_text': 'Header Text {{1}}'})
        self.assertFalse(template.header_attachment_id, 'Text header: should reset attachments')

        template.write({'header_type': 'image', 'header_attachment_id': self.image_attachment_wa_admin.id})
        self.assertFalse(template.header_text, 'Image header: should reset text header')
        self.assertEqual(template.header_attachment_id.res_model, template._name)
        self.assertEqual(template.header_attachment_id.res_id, template.id)

    @users('user_wa_admin')
    def test_template_header_text_required(self):
        with self.assertRaises(exceptions.ValidationError):
            self.env['whatsapp.test.base.template'].create({
                'body': 'Test template',
                'header_type': 'text',
                'name': 'Header text template',
            })


@tagged('wa_template')
class WhatsAppBaseTemplateInternals(WhatsAppCommon):
    """Tests for WhatsApp template internals: attachment relinking and copy behavior."""

    @users('user_wa_admin')
    def test_attachment_ownership_on_write(self):
        """ Test that writing a header attachment keeps one the template already owns,
        as the many2one_binary widget uploads it with the record already set, and copies
        one belonging to another template. """
        template = self.env['whatsapp.test.base.template'].create({
            'body': 'Test write ownership',
            'header_attachment_id': self.document_attachment_wa_admin.id,
            'header_type': 'document',
            'name': 'Test Write Ownership',
        })
        owned = template.header_attachment_id
        template.write({'header_attachment_id': owned.id})
        self.assertEqual(template.header_attachment_id, owned)

        other = self.env['whatsapp.test.base.template'].create({
            'body': 'Test write steal',
            'header_attachment_id': self.image_attachment_wa_admin.id,
            'header_type': 'image',
            'name': 'Test Write Steal',
        })
        other.write({'header_type': 'document', 'header_attachment_id': owned.id})
        self.assertNotEqual(other.header_attachment_id, owned)
        self.assertEqual(other.header_attachment_id.res_id, other.id)
        self.assertEqual(owned.res_id, template.id)

    @users('user_wa_admin')
    def test_copy_attachments(self):
        """Ensure header attachments are copied and relinked to the new template (res_model and res_id)."""
        template = self.env['whatsapp.test.base.template'].create({
            'body': 'Test body',
            'header_attachment_id': self.document_attachment_wa_admin.id,
            'header_type': 'document',
            'name': 'Test Copy Document Header',
        })
        clone = template.copy()
        self.assertEqual(template.header_attachment_id.res_model, template._name)
        self.assertEqual(template.header_attachment_id.res_id, template.id)
        self.assertEqual(clone.header_attachment_id.res_id, clone.id)
        self.assertEqual(clone.header_attachment_id.res_model, clone._name)
        self.assertNotEqual(template.header_attachment_id, clone.header_attachment_id)
