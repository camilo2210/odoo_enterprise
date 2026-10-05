# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PaymentToken(models.Model):
    _inherit = 'payment.token'

    def _handle_archiving(self):
        """ Override of payment to void the token on linked subscriptions.

        :return: None
        """
        super()._handle_archiving()

        linked_subscriptions = self.env['sale.order'].search([('payment_token_id', 'in', self.ids)])
        linked_subscriptions.write({'payment_token_id': None})

    def get_linked_records_info(self):
        """ Override of payment to add information about subscriptions linked to the current token.

        Note: self.ensure_one()
        The 'prepayment_percent' filter allows removing tokens linked to subscriptions which don't have required payment.

        :return: The list of information about linked subscriptions
        :rtype: list
        """
        res = super().get_linked_records_info()
        subscriptions = self.env['sale.order'].search([('payment_token_id', '=', self.id), ('prepayment_percent', '>', 0)])
        for sub in subscriptions:
            res.append({
                'description': subscriptions._description,
                'id': sub.id,
                'name': sub.name,
                'url': sub.get_portal_url(),
                'active_subscription': sub.subscription_state in ['3_progress', '4_paused'],
            })
        return res
