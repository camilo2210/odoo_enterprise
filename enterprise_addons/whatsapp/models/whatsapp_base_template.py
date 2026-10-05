from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WhatsappBaseTemplate(models.AbstractModel):
    _name = 'whatsapp.base.template'
    _inherit = ['mail.thread']
    _description = 'WhatsApp Base Template'

    name = fields.Char(string='Name', tracking=True)
    active = fields.Boolean(default=True)

    body = fields.Text(string='Template body', tracking=True, required=True)
    header_type = fields.Selection([
        ('none', 'None'),
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document')], string='Header Type', default='none')
    header_text = fields.Char(
        string='Template Header Text',
        compute='_compute_header_text', readonly=False, store=True, precompute=True)
    header_attachment_id = fields.Many2one(
        'ir.attachment', string='Template Static Header',
        bypass_search_access=True,
        compute='_compute_header_attachment_id', readonly=False, store=True,
        copy=False)  # keep False to avoid linking attachments; we have to copy them instead
    footer_text = fields.Char(string='Footer Message')
    allowed_user_ids = fields.Many2many(
        comodel_name='res.users', string="Users",
        domain=[('share', '=', False)])

    @api.constrains('header_attachment_id', 'header_type')
    def _check_header_attachment_id(self):
        templates_with_attachments = self.filtered('header_attachment_id')
        for tmpl in templates_with_attachments:
            if tmpl.header_type not in ['image', 'video', 'document']:
                raise ValidationError(_("Only templates using media header types may have header documents"))
            supported_mimetypes = self.env['whatsapp.message']._SUPPORTED_ATTACHMENT_TYPE[tmpl.header_type]
            if tmpl.header_attachment_id.mimetype not in supported_mimetypes:
                raise ValidationError(_("File type %(file_type)s not supported for header type %(header_type)s",
                                        file_type=tmpl.header_attachment_id.mimetype, header_type=tmpl.header_type))
        for tmpl in self - templates_with_attachments:
            if tmpl.header_type in ['image', 'video', 'document']:
                raise ValidationError(_('Header document is required'))

    @api.constrains('header_text', 'header_type')
    def _check_header_text(self):
        for tmpl in self.filtered(lambda tmpl: tmpl.header_type == 'text'):
            if not tmpl.header_text:
                raise ValidationError(_('Header Text is required for text headers.'))
            if len(tmpl.header_text) > 60:
                raise ValidationError(_('Header Text cannot exceed 60 characters.'))

    @api.depends('header_type')
    def _compute_header_text(self):
        toreset_text = self.filtered(lambda t: t.header_type != 'text')
        if toreset_text:
            toreset_text.header_text = False

    @api.depends('header_type')
    def _compute_header_attachment_id(self):
        toreset_attachments = self.filtered(lambda t: t.header_type not in ['image', 'video', 'document'])
        if toreset_attachments:
            toreset_attachments.header_attachment_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._link_header_attachment()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'header_attachment_id' in vals:
            self._link_header_attachment()
        return res

    def copy_data(self, default=None):
        default = {} if default is None else default
        values_list = super().copy_data(default=default)

        for values, template in zip(values_list, self):
            if not values.get('header_attachment_id') and template.header_attachment_id:
                # Pass the existing attachment to create(), which handles copying it when it
                # already belongs to another record.
                values['header_attachment_id'] = template.header_attachment_id.id
        return values_list

    def _link_header_attachment(self):
        """ Make each template own its header attachment.

        An attachment belongs to a single record, so a free one is taken over and
        one already owned elsewhere is copied. That is what lets copy_data simply
        hand over the original id.
        """
        for tmpl in self.filtered('header_attachment_id'):
            attachment = tmpl.header_attachment_id
            if attachment.res_model == tmpl._name and attachment.res_id == tmpl.id:
                continue
            if not attachment.res_id and attachment.res_model in (False, tmpl._name):
                attachment.write({'res_id': tmpl.id, 'res_model': tmpl._name})
            else:
                tmpl.header_attachment_id = attachment.copy({
                    'res_id': tmpl.id,
                    'res_model': tmpl._name,
                    'res_field': False,
                })
