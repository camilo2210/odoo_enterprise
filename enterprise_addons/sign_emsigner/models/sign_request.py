# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import ValidationError


class SignRequest(models.Model):
    _inherit = "sign.request"

    @api.constrains('request_item_ids')
    def _check_no_emsigner_with_external_signature(self):
        """ Aadhaar signs a document of its own, built from the template, so it cannot share
        a request with a signer whose signature seals the working copy.

        TODO: drop this once Aadhaar signs through the external signature flow of `sign`,
        which needs its proxy to sign a digest and return the CMS value instead of signing
        a whole document of its own.
        """
        for sign_request in self:
            roles = sign_request.request_item_ids.role_id
            if any(role.auth_method == 'emsigner' for role in roles) and any(roles.mapped('requires_external_signature')):
                raise ValidationError(self.env._(
                    "A signer using Aadhaar cannot be part of a request that is signed with a qualified signature."))

    def _check_sign_order_with_emsigner(self, request_item):
        """Prevent signing if any sign request item have emsigner as auth_method and it's not the current user's turn."""
        pending_item = self.request_item_ids.filtered(
            lambda r: r.mail_sent_order < request_item.mail_sent_order and r.state != 'completed'
        )
        return pending_item

    def go_to_signable_document(self, request_items=None):
        """ Go to the signable document as the signers or the current user for specified request_items. """
        res = super().go_to_signable_document(request_items)

        if self.env.context.get('sign_all') or all(role.auth_method != 'emsigner' for role in self.request_item_ids.role_id):
            return res

        if not request_items:
            request_items = self.request_item_ids.filtered(
                lambda r: not r.partner_id or (r.state == 'sent' and r.partner_id.id == self.env.user.partner_id.id)
            )[0]

        if not request_items:
            return res

        pending_item = self._check_sign_order_with_emsigner(request_items)
        if pending_item:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'sticky': False,
                    'message': self.env._("Emsigner role cannot be used for signing directly. Please send the request instead."),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        return res

    def go_to_document(self):
        self.ensure_one()
        res = super().go_to_document()

        if self.state != "sent" or all(role.auth_method != 'emsigner' for role in self.request_item_ids.role_id):
            return res

        request_item = self.request_item_ids.filtered(
            lambda r: not r.partner_id or (r.state == 'sent' and r.partner_id == self.env.user.partner_id)
        )[:1]

        pending_item = self._check_sign_order_with_emsigner(request_item)
        if pending_item:
            res['context']['need_to_sign'] = False
        return res
