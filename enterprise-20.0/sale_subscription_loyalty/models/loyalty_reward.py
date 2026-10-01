# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    recurring_invoice = fields.Boolean(
        string="Recurring",
        help="Reward will be applied for each renewed period if enough points.",
    )

    @api.constrains('recurring_invoice', 'program_id')
    def _check_recurring_invoice(self):
        for reward in self:
            if reward.recurring_invoice and reward.program_type in ('gift_card', 'ewallet'):
                raise ValidationError(_("The recurring option on a loyalty reward is not available for Gift Card and eWallet program types."))

    def _get_recurring_rewards(self):
        """ Returns the rewards records that are active and recurring. """
        return self.search([('recurring_invoice', '=', True), ('active', '=', True)])

    def _get_reward_products(self):
        """ Returns the rewards products according to the type of the reward. """
        self.ensure_one()
        if self.reward_type == 'discount':
            reward_products_ids = self.discount_line_product_id.ids
        else:
            reward_products_ids = self.reward_product_ids.ids
        return reward_products_ids
