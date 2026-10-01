# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    sign_signature_data = fields.Binary(string="Digital Signature", copy=False, groups="base.group_system")
    sign_initials_data = fields.Binary(string="Digital Initials", copy=False, groups="base.group_system")
    sign_signature_frame = fields.Binary(string="Digital Signature Frame", copy=False, groups="base.group_system")
    sign_initials_frame = fields.Binary(string="Digital Initials Frame", copy=False, groups="base.group_system")

    sign_signature = fields.Binary(compute='_compute_sign_signature', inverse='_inverse_sign_signature', groups='base.group_user', user_writeable=True)
    sign_initials = fields.Binary(compute='_compute_sign_initials', inverse='_inverse_sign_initials', groups='base.group_user', user_writeable=True)

    def _check_accessible_signature_users(self):
        if self.env.su or self == self.env.user or self.env.user.has_group('base.group_system'):
            return
        raise AccessError(self.env._("Cannot read the signature of other users"))

    @api.depends('sign_signature_data')
    @api.depends_context('uid')
    def _compute_sign_signature(self):
        self._check_accessible_signature_users()
        for user in self:
            user.sign_signature = user.sudo().sign_signature_data

    def _inverse_sign_signature(self):
        self._check_accessible_signature_users()
        for user in self:
            user.sudo().sign_signature_data = user.sign_signature

    @api.depends('sign_initials_data')
    @api.depends_context('uid')
    def _compute_sign_initials(self):
        self._check_accessible_signature_users()
        for user in self:
            user.sign_initials = user.sudo().sign_initials_data

    def _inverse_sign_initials(self):
        self._check_accessible_signature_users()
        for user in self:
            user.sudo().sign_initials_data = user.sign_initials
