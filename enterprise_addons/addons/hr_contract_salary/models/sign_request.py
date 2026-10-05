from odoo import models


class SignRequest(models.Model):
    _inherit = 'sign.request'

    def cancel(self):
        super().cancel()
        # sudo(), as not everyone has access to 'hr.contract.salary.offer'
        # but they should be able to cancel their sign request
        offers_sudo = self.env['hr.contract.salary.offer'].sudo().search([('sign_request_ids', 'in', self.ids)])
        offers_sudo.unlink_archived_version_offer()
        offers_sudo.write({'state': 'cancelled'})
        for offer in offers_sudo:
            offer.message_post(body=self.env._("The offer has been cancelled due to the signature request cancellation."))

    def write(self, vals):
        old_states = {req.id: req.state for req in self}
        res = super().write(vals)
        self.filtered(
            lambda request: request.state == 'canceled' and old_states.get(request.id) != 'canceled'
        ).activity_unlink(['sign.mail_activity_data_signature_request'])
        return res
