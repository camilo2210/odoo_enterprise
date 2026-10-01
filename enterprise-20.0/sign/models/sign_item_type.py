# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.fields import Command, Domain
from odoo.exceptions import UserError, ValidationError


class SignItemType(models.Model):
    _name = 'sign.item.type'
    _description = "Signature Item Type"

    active = fields.Boolean("Active", default=True)
    name = fields.Char(string="Field Name", required=True, translate=True)
    icon = fields.Char()
    item_type = fields.Selection([
        ('signature', "Signature"),
        ('initial', "Initial"),
        ('text', "Text"),
        ('textarea', "Multiline Text"),
        ('checkbox', "Checkbox"),
        ('radio', "Radio"),
        ('selection', "Selection"),
        ('strikethrough', "Strikethrough"),
        ('stamp', "Stamp"),
        ('date', "Date"),
    ], required=True, string='Type', default='text')

    tip = fields.Char(required=True, default="Fill in", help="Hint displayed in the signing hint", translate=True)
    placeholder = fields.Char(translate=True)

    field_size = fields.Selection([
            ('short_text', "Short Text"),
            ('regular_text', "Regular Text"),
            ('long_text', "Long Text"),
        ], string="Field Size", default='regular_text', required=True,
    )
    default_width = fields.Float(string="Default Width", digits=(4, 3), required=True, default=0.150, compute="_compute_dimensions")
    default_height = fields.Float(string="Default Height", digits=(4, 3), required=True, default=0.015, compute="_compute_dimensions")
    model_id = fields.Many2one('ir.model', string="Linked to",
                                domain=[('model', '!=', 'sign.request'), ('is_mail_thread', '=', True)])
    model_name = fields.Char(related='model_id.model')
    auto_field = fields.Char(string="Linked field", groups='base.group_system',
                             help="Technical name of the field on the partner model to auto-complete this signature field at the time of signature.")
    auto_write = fields.Boolean("Update Field", groups='base.group_system', default=False,
                                    help="If checked, the value filled during signing will be written back to the corresponding field using sender permissions.")
    required = fields.Boolean(string="Mandatory", compute='_compute_required', store=True, readonly=False)
    alignment = fields.Selection([
            ('left', 'Left'),
            ('center', 'Center'),
            ('right', 'Right')
        ], default="left")
    constant = fields.Boolean(string="Read-only")
    custom = fields.Boolean(string="Custom Item Type", default=True, readonly=True)
    shared = fields.Boolean(string="Shared", default=False, help="Make this field available for everyone.")
    authorized_users = fields.Many2many(
        'res.users', relation='sign_item_type_res_users_rel', string="Authorized Users", readonly=True,
        help="Additional users that can use this custom field while editing templates.",
    )
    authorized_group_ids = fields.Many2many(
        'res.groups', relation='sign_item_type_res_groups_rel', string="Used by",
        help="Additional groups that can use this field while editing templates.",
    )

    @api.constrains('auto_field')
    def _check_auto_field_exists(self):
        for sign_type in self:
            if sign_type.auto_field and sign_type.model_id.model:
                record = self.env[sign_type.model_id.model]
                try:
                    auto_field_value = record.mapped(sign_type.auto_field)
                except KeyError:
                    auto_field_value = None
                if auto_field_value is None or isinstance(auto_field_value, models.BaseModel):
                    raise ValidationError(_("Malformed expression: %(exp)s", exp=sign_type.auto_field))

    @api.constrains('auto_field', 'model_id', 'auto_write')
    def _check_auto_write_requires_field_and_model(self):
        for item_type in self:
            if item_type.auto_write and not (item_type.model_id and item_type.auto_field):
                raise ValidationError(self.env._("'Update Field' requires both a linked model and a linked field to be set."))

    @api.constrains('auto_field', 'model_id', 'auto_write')
    def _check_x2many_in_auto_field(self):
        """ Prevents users from enabling two-way sync on paths that contain
        multiple records (One2many/Many2many), which would crash the sync.
        """
        for item_type in self:
            if not (item_type.auto_field and item_type.model_id and item_type.auto_write):
                continue

            current_model = self.env[item_type.model_id.model]
            parts = item_type.auto_field.split('.')

            # Walk through every part of the path
            for part in parts:
                field_rec = current_model._fields.get(part)

                if not field_rec:
                    break

                # If we hit a multi-record relation anywhere
                if field_rec.type in ('one2many', 'many2many'):
                    raise ValidationError(_(
                        "You cannot link the model '%(model)s' on the path '%(path)s'.\n\n"
                        "The field/relationship '%(field)s' contains multiple records (%(type)s), "
                        "which cannot be directly linked to an updatable sign item.",
                        model=item_type.model_id.model,
                        path=item_type.auto_field,
                        field=part,
                        type=field_rec.type
                    ))

                # Step into the related model for the next loop iteration.
                if field_rec.relational:
                    current_model = self.env[field_rec.comodel_name]

    @api.depends('field_size', 'item_type')
    def _compute_dimensions(self):
        text_dimension_map = {
            'short_text': {'width': 0.1, 'height': 0.015},
            'regular_text': {'width': 0.18, 'height': 0.015},
            'long_text': {'width': 0.3, 'height': 0.015},
        }

        default_dimension_map = {
            'signature': [0.2, 0.05],
            'initial': [0.085, 0.03],
            'text': [0.18, 0.015],
            'textarea': [0.2, 0.05],
            'checkbox': [0.02, 0.018],
            'radio': [0.02, 0.018],
            'selection': [0.18, 0.015],
            'strikethrough': [0.18, 0.015],
            'stamp': [0.298, 0.092],
            'date': [0.18, 0.015],
        }

        for record in self:
            if record.item_type == 'text':
                dimensions = text_dimension_map.get(record.field_size, {})
                record.default_width = dimensions.get('width', record.default_width)
                record.default_height = dimensions.get('height', record.default_height)
            else:
                record.default_width = default_dimension_map[record.item_type][0]
                record.default_height = default_dimension_map[record.item_type][1]

    @api.depends('item_type')
    def _compute_required(self):
        for rec in self:
            rec.required = rec.item_type not in ['checkbox', 'strikethrough', 'textarea']

    def _add_authorized_users(self, users):
        """ Add the given users to the authorized list of custom sign item types.
        This is additive and never removes existing users. Non-custom types are ignored. """
        custom_types = self.filtered('custom')
        if not custom_types or not users:
            return
        custom_types.sudo().write({'authorized_users': [Command.link(user.id) for user in users]})

    @api.model
    def get_sidebar_item_types(self, template_id, domain=None):
        """Return the item types visible in the fields sidebar for the current user. Also
        includes any type that's already placed on template_id, even if the user
        would not normally be allowed to use it.

        :param template_id: id of the sign.template
        :param domain: extra domain to combine with the visibility domain
        :return: list of dicts, as returned by search_read
        """
        fields = ['id', 'name', 'icon', 'item_type', 'alignment', 'constant', 'required', 'default_width', 'default_height', 'placeholder']

        user = self.env.user
        # The visibility domain is a combination of the following:
        # 1. Shared types are always visible.
        # 2. Non-shared types with no groups/users set are only visible to their creator.
        # 3. Non-shared types are visible to users in authorized_group_ids or authorized_users.
        accessible_by_creator = Domain.AND([
            Domain('authorized_group_ids', '=', False),
            Domain('authorized_users', '=', False),
            Domain('create_uid', '=', user.id),
        ])
        visibility_domain = Domain.OR([
            Domain('shared', '=', True),
            accessible_by_creator,
            Domain('authorized_group_ids', 'in', user.all_group_ids.ids),
            Domain('authorized_users', 'in', user.id),
        ])
        domain = Domain.AND([domain or [], visibility_domain])
        results = self.search_read(domain, fields)

        template = self.env['sign.template'].browse(template_id)
        missing_ids = set(template.sign_item_ids.type_id.ids) - {vals['id'] for vals in results}
        if missing_ids:
            # if already on the template, give access to them
            results += self.sudo().browse(missing_ids).read(fields)

        return results

    def write(self, vals):
        if 'auto_write' in vals and len(self) > 1:
            raise UserError(_("Mass editing is not allowed for the 'Update Field'. Please edit records individually."))

        return super().write(vals)

    @api.onchange('item_type')
    def _onchange_item_type(self):
        if not self.item_type in ['text', 'textarea', 'date']:
            self.auto_field = False
            self.auto_write = False
            self.model_id = False
