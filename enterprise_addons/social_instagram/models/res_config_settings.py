# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    instagram_use_own_account = fields.Boolean("Use your own Instagram Account", config_parameter='social.instagram_use_own_account',
        help="""Check this if you want to use your personal Instagram Developer Account instead of the provided one.""")
    instagram_app_id = fields.Char("Instagram App ID",
        compute='_compute_instagram_app_id', inverse='_inverse_instagram_app_id')
    instagram_client_secret = fields.Char("Instagram App Secret",
        compute='_compute_instagram_client_secret', inverse='_inverse_instagram_client_secret')
    instagram_webhook_verify_token = fields.Char("Instagram Webhook Verify Token",
        compute='_compute_instagram_webhook_verify_token', inverse='_inverse_instagram_webhook_verify_token')

    @api.depends('instagram_use_own_account')
    def _compute_instagram_app_id(self):
        for record in self:
            if record._instagram_use_and_check_own_account():
                record.instagram_app_id = self.env['ir.config_parameter'].sudo().get_str('social.instagram_app_id') or False
            else:
                record.instagram_app_id = False

    def _inverse_instagram_app_id(self):
        for record in self:
            if record._instagram_use_and_check_own_account():
                self.env['ir.config_parameter'].sudo().set_str('social.instagram_app_id', record.instagram_app_id or None)
            elif self.env.user.has_group('social.group_social_manager'):
                self.env['ir.config_parameter'].sudo().set_str('social.instagram_app_id', None)

    @api.depends('instagram_use_own_account')
    def _compute_instagram_client_secret(self):
        for record in self:
            if record._instagram_use_and_check_own_account():
                record.instagram_client_secret = self.env['ir.config_parameter'].sudo().get_str('social.instagram_client_secret') or False
            else:
                record.instagram_client_secret = False

    def _inverse_instagram_client_secret(self):
        for record in self:
            if record._instagram_use_and_check_own_account():
                self.env['ir.config_parameter'].sudo().set_str('social.instagram_client_secret', record.instagram_client_secret or None)
            elif self.env.user.has_group('social.group_social_manager'):
                self.env['ir.config_parameter'].sudo().set_str('social.instagram_client_secret', None)

    @api.depends('instagram_use_own_account')
    def _compute_instagram_webhook_verify_token(self):
        for record in self:
            if record._instagram_use_and_check_own_account():
                record.instagram_webhook_verify_token = self.env['ir.config_parameter'].sudo().get_str(
                    'social.instagram_webhook_verify_token') or False
            else:
                record.instagram_webhook_verify_token = False

    def _inverse_instagram_webhook_verify_token(self):
        for record in self:
            if record._instagram_use_and_check_own_account():
                self.env['ir.config_parameter'].sudo().set_str(
                    'social.instagram_webhook_verify_token',
                    record.instagram_webhook_verify_token)
            elif self.env.user.has_group('social.group_social_manager'):
                self.env['ir.config_parameter'].sudo().set_str('social.instagram_webhook_verify_token', None)

    def _instagram_use_and_check_own_account(self):
        return self.env.user.has_group('social.group_social_manager') and self.instagram_use_own_account
