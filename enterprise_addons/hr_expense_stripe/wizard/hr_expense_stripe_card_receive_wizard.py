from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.hr_expense_stripe.utils import make_request_stripe_proxy


class HrExpenseStripeCardReceiveWizard(models.TransientModel):
    _name = 'hr.expense.stripe.card.receive.wizard'
    _inherit = 'mail.track.mixin'
    _description = 'A wizard used to first active a card when received'

    card_id = fields.Many2one(comodel_name='hr.expense.stripe.card', string='Card to activate', required=True)
    card_last_4 = fields.Char(related='card_id.last_4')

    last_4_challenge = fields.Char(
        string='Card Last 4 digits',
        help='The last 4 digits of the card you received. This is used to confirm that you have received the correct card.',
        size=4
        # not required to not block the user when opening the terms wizard
    )
    phone_number = fields.Char(
        string='Cardholder Mobile Number',
        help='Viewing confidential card details requires 2FA authentication. Make sure the cardholder mobile number is correct.',
        required=True,
        tracking=True,
    )

    is_confirmed = fields.Boolean(default=False, required=True)
    original_phone_number = fields.Char(required=True, tracking=True)
    billing_country_code = fields.Char(required=True)

    show_warning_wrong_last_4 = fields.Boolean(compute='_compute_show_warning_wrong_last_4')

    @api.depends('last_4_challenge', 'card_last_4')
    def _compute_show_warning_wrong_last_4(self):
        for wizard in self:
            wizard.show_warning_wrong_last_4 = wizard.last_4_challenge and wizard.last_4_challenge != wizard.card_last_4

    def _track_phone_number_change(self):
        self.ensure_one()
        # Get the cardholder cards that belong to the same company
        cardholder_user_su = self.sudo().card_id.employee_id.user_id
        field_id = self.env['ir.model.fields']._get(self._name, 'phone_number').id
        cards_su = cardholder_user_su.stripe_card_ids.filtered(lambda card: card.company_id == self.card_id.company_id)
        cards_su._track_add(
            {card_su.id: {'phone_number': self.original_phone_number} for card_su in cards_su},
            end_values={card_su.id: {'phone_number': self.phone_number} for card_su in cards_su},
            fields_info={'phone_number': {'field_id': field_id, 'type': 'char'}},
        )
        # send now tracking messages
        cards_su._track_finalize()

    def open_expense_stripe_card_receive_terms(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'hr_expense_stripe.expense_stripe_card_receive_terms',
        }

    def action_receive_card(self):
        for wizard in self:
            if not wizard.is_confirmed:
                raise UserError(self.env._("You must confirm that you have received the card before activating it."))

            if wizard.last_4_challenge != wizard.card_last_4:
                raise UserError(self.env._(
                    "The last 4 digits you entered do not match the card you received. Please check and try again."
                ))

            if wizard.phone_number != wizard.original_phone_number:
                # Update the phone number on Stripe if the user gave a different one
                billing_country = self.env['res.country'].search(
                    domain=[('code', 'ilike', wizard.billing_country_code)],
                    limit=1,
                )
                phone_number = wizard.card_id.employee_id._phone_format(
                    number=wizard.phone_number,
                    country=billing_country,
                    force_format='E164',
                )

                make_request_stripe_proxy(
                    wizard.card_id.company_id.sudo(),
                    'cardholders/{cardholder_id}',
                    route_params={'cardholder_id': wizard.card_id.employee_id.sudo().private_stripe_id},
                    payload={'account': wizard.card_id.company_id.sudo().stripe_id, 'phone_number': phone_number},
                    method='POST',
                )
                wizard._track_phone_number_change()

            card_sudo = wizard.card_id.sudo(wizard.card_id.employee_id.user_id == self.env.user or self.env.su)
            card_sudo.is_delivered = True
            card_sudo._create_or_update_card(state='active')
