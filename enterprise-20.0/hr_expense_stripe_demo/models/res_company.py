from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import RedirectWarning, UserError

from odoo.addons.hr_expense_stripe.utils import COUNTRY_MAPPING, make_request_stripe_proxy

# Some postal codes in the demo data aren't supported by Stripe
# Such as 35043 in France which is used for large businesses or specific delivery points.
# Or the format isn't specific enough like in the Netherlands which needs the 2 letter at the end.
POSTAL_CODE_OVERRIDES = {
    'IT': '13019',
    'FI': '22410',
    'FR': '44100',
    'NL': '9712 LE',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_account_creation_payload(self):
        """ Create a fully prepared Stripe account to quickly test the HR Expense Stripe integration. """
        if self.env['ir.config_parameter'].sudo().get_str('hr_expense_stripe.stripe_mode') == 'live':
            return super()._get_account_creation_payload()

        self.ensure_one()
        country_code = COUNTRY_MAPPING.get(self.country_id.code, self.country_id.code)
        postal_code = POSTAL_CODE_OVERRIDES.get(country_code, self.zip)
        if not postal_code:
            raise RedirectWarning(
                message=self.env._("To create a Stripe account for your company, please set a postal code on your company address."),
                action=self._get_records_action(),
                button_text=self.env._("Configure Company"),
            )
        return {
            'business_profile[annual_revenue][amount]': '500000',
            'business_profile[annual_revenue][currency]': self.stripe_currency_id.name,
            'business_profile[annual_revenue][fiscal_year_end]': (fields.Date.context_today(self).replace(month=1, day=1) - timedelta(days=1)).isoformat(),
            'business_profile[estimated_worker_count]': '7274',
            'business_profile[mcc]': '5598',
            'business_profile[name]': self.name or 'match_name_relationships',
            'business_profile[product_description]': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
            'business_profile[support_phone]': '0000000000',
            'business_type': 'individual',
            'company[address][city]': 'City',
            'company[address][country]': country_code,
            'company[address][line1]': 'address_full_match',
            'company[address][postal_code]': postal_code,
            'company[address][state]': 'State',
            'company[name]': self.name or 'match_name_relationships',
            'company[phone]': '0000000000',
            'company[tax_id]': 'HRB 12345' if self.country_id.code == 'DE' else '222222222',
            'country': country_code,
            'email': 'demo@example.com',
            'external_account': 'btok_' + country_code.lower(),
            'settings[card_issuing][tos_acceptance][date]': int(fields.Datetime.now().timestamp()),
            'settings[card_issuing][tos_acceptance][ip]': '127.0.0.1',
            'tos_acceptance[date]': int(fields.Datetime.now().timestamp()),
            'tos_acceptance[ip]': '127.0.0.1',
        }

    def action_create_stripe_demo_account(self):
        """ Quickly create a Stripe account by creating one with default/demo data if none exists yet. """

        if not self.env['ir.config_parameter'].sudo().get_str('hr_expense_stripe.stripe_mode') == 'test':
            raise UserError(self.env._("Demo Stripe accounts can only be created in test mode."))
        self.action_create_stripe_account()

        make_request_stripe_proxy(
            self.sudo(),
            'test_helpers/account_verify',
            payload={'account': self.sudo().stripe_id},
            method='POST'
        )
