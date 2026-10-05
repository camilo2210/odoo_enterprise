from copy import deepcopy
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import OrderedSet

from odoo.addons.hr_expense_stripe.utils import STRIPE_3D_SECURE_LOCALES, make_request_stripe_proxy


class HrExpenseStripeCardholderWizard(models.TransientModel):
    _name = 'hr.expense.stripe.cardholder.wizard'
    _inherit = 'mail.thread'
    _description = 'Wizard to configure the cardholder'

    # DEV warning, due to the fact that we're using the tracking values to make the diff between stripe values and the new tracked ones,
    # We should be extra cautious not to use computed or inverse fields in order not to pollute the card chatter with nonsense

    # Untracked fields
    card_id = fields.Many2one(comodel_name='hr.expense.stripe.card', string="Card", readonly=True)
    company_id = fields.Many2one(comodel_name='res.company', string="Company", readonly=True)
    employee_id = fields.Many2one(comodel_name='hr.employee', string="Employee", readonly=True)
    company_country_id = fields.Many2one(
        related="company_id.country_id",
        string="Company Country",
        readonly=True,
    )
    stripe_values = fields.Json()  # Used for the tracking data original values

    # Tracked Fields
    firstname = fields.Char(string="First Name", tracking=True)
    lastname = fields.Char(string="Last Name", tracking=True)

    email = fields.Char(string="Email", tracking=True)
    phone_number = fields.Char(string="Phone Number", tracking=True)  # EU required
    birthday = fields.Date(string="Birthday", tracking=True)

    billing_city = fields.Char(string="City", tracking=True)
    billing_country_id = fields.Many2one(comodel_name='res.country', string="Country", tracking=True)
    billing_street = fields.Char(string="Street", tracking=True)
    billing_street2 = fields.Char(string="Street 2", tracking=True)
    billing_state_id = fields.Many2one(
        comodel_name='res.country.state',
        string="State",
        domain='[("country_id", "=", billing_country_id)]',
        tracking=True,
    )  # US required
    company_country_code = fields.Char(related='company_country_id.code', string="Company Country Code", readonly=True)
    billing_zip = fields.Char(string="Zip", tracking=True)

    @api.model
    def _create_from_card(self, employee, company, card):
        card.check_access('write')
        # Ensure access to the employee fields. The card manager should have a read access to the required employee fields
        employee_sudo = employee.sudo()
        employee_stripe_id = employee_sudo.private_stripe_id
        create_vals = {
            'employee_id': employee_sudo.id,
            'company_id': company.id,
            'card_id': card.id,
        }
        tracked_create_vals = {}

        if employee_stripe_id:
            response = make_request_stripe_proxy(
                company.sudo(),
                'cardholders/{cardholder_id}',
                route_params={'cardholder_id': employee_stripe_id},
                payload={'account': company.sudo().stripe_id},
                method='GET',
            )

            tracked_create_vals['firstname'] = response['individual']['first_name']
            tracked_create_vals['lastname'] = response['individual']['last_name']

            tracked_create_vals['email'] = response['email']
            tracked_create_vals['phone_number'] = response['phone_number']
            year = response['individual']['dob']['year']
            month = response['individual']['dob']['month']
            day = response['individual']['dob']['day']
            # VERY IMPORTANT, the ORM will convert it but not the JSON
            tracked_create_vals['birthday'] = date(year=year, month=month, day=day).isoformat()

            billing_adress = response['billing']['address']
            country = self.env['res.country'].search([('code', 'ilike', billing_adress['country'])], limit=1)
            tracked_create_vals['billing_country_id'] = country.id
            tracked_create_vals['billing_city'] = billing_adress['city']
            tracked_create_vals['billing_street'] = billing_adress['line1']
            tracked_create_vals['billing_zip'] = billing_adress['postal_code']
            if billing_adress['line2']:
                tracked_create_vals['billing_street2'] = billing_adress['line2']
            if billing_adress['state']:
                state = self.env['res.country.state'].search([('code', '=', billing_adress['state'])], limit=1)
                if not state:  # We previously stored the name of the state, so Stripe might still have the name instead of the code
                    state = self.env['res.country.state'].search([('name', 'ilike', billing_adress['state'])], limit=1)
                tracked_create_vals['billing_state_id'] = state.id or False
            create_vals['stripe_values'] = deepcopy(tracked_create_vals)

        else:
            # Try prefill from Employee
            private_first_name, *private_last_name = (employee_sudo.name or '').split(' ')
            tracked_create_vals['firstname'] = private_first_name
            tracked_create_vals['lastname'] = ' '.join(private_last_name)

            tracked_create_vals['email'] = employee_sudo.email
            tracked_create_vals['phone_number'] = employee_sudo.work_phone
            tracked_create_vals['birthday'] = employee_sudo.birthday and employee_sudo.birthday.isoformat()  # VERY IMPORTANT, the ORM will convert it but not the JSON

            work_address = employee_sudo.address_id
            tracked_create_vals['billing_country_id'] = work_address.country_id and work_address.country_id.id
            tracked_create_vals['billing_city'] = work_address.city

            tracked_create_vals['billing_street'] = work_address.street
            tracked_create_vals['billing_street2'] = work_address.street2
            tracked_create_vals['billing_zip'] = work_address.zip
            tracked_create_vals['billing_state_id'] = work_address.state_id and work_address.state_id.id

            # As it doesn't exist on Stripe
            tracked_create_vals['stripe_values'] = {field_name: False for field_name in tracked_create_vals}

        return self.create([{**create_vals, **tracked_create_vals}])

    def _track_prepare(self, field_names):
        # EXTEND mail to force custom initial_values
        initial_values = super()._track_prepare(field_names)
        if initial_values is None:
            return
        for wizard in self:
            record_initial_values = initial_values.get(wizard.id)
            if not record_initial_values:
                continue
            for field_name, value in (wizard.stripe_values or {}).items():
                if field_name not in record_initial_values:
                    continue
                match field_name:
                    case 'billing_country_id':  # relational model field stored as an integer in the json
                        record_initial_values[field_name] = self.env['res.country'].browse(value)
                    case 'billing_state_id':
                        record_initial_values[field_name] = self.env['res.country.state'].browse(value)
                    case 'birthday':  # Stored as an iso-format string in the json
                        record_initial_values[field_name] = value and date.fromisoformat(value)
                    case _:
                        record_initial_values[field_name] = value
        return initial_values

    def action_save_cardholder(self):
        self.ensure_one()
        self.card_id.check_access('write')
        employee_sudo = self.employee_id.sudo()
        # Create the ordered list of user languages for the 3DSecure flow
        preferred_langs = OrderedSet()
        user_lang = employee_sudo.user_id.lang and employee_sudo.user_id.lang.split('_')[0]
        preferred_langs.add(user_lang)
        employee_lang = employee_sudo.lang and employee_sudo.lang.split('_')[0]
        preferred_langs.add(employee_lang)
        preferred_langs.add('en')
        preferred_langs.discard(False)
        payload = {
            'account': self.company_id.sudo().stripe_id,
            'lang': employee_sudo.user_id.lang or employee_sudo.lang or 'en_US',  # Default to en_US if no lang is set
            'billing': {
                'address': {
                    'country': self.billing_country_id.code,
                    'city': self.billing_city,
                    'line1': self.billing_street,
                    'postal_code': self.billing_zip,
                }
            },
            'name': f'{self.firstname} {self.lastname}',
            'email': self.email,
            'individual': {
                'dob': {
                    'day': self.birthday.day,
                    'month': self.birthday.month,
                    'year': self.birthday.year,
                },
                'first_name': self.firstname,
                'last_name': self.lastname,
            },
            'preferred_locales': [lang for lang in preferred_langs if lang in STRIPE_3D_SECURE_LOCALES],
        }
        phone_number = employee_sudo._phone_format(
            number=self.phone_number,
            country=self.billing_country_id,
            force_format='E164',
        )
        if phone_number:
            payload['phone_number'] = phone_number
        else:
            raise UserError(_("The phone number is invalid."))

        # Add non mandatory fields
        if self.billing_street2:
            payload['billing']['address']['line2'] = self.billing_street2
        if self.billing_state_id:
            # Stripe uses the ISO 3166-2 for the state for the US. However, Odoo doesn't use the ISO 3611-2 for all the countries
            # But the ISO 3166-2 is used for the US states in Odoo and Stripe doesn't check it for the others (EU/UK) so we can safely use it.
            payload['billing']['address']['state'] = self.billing_state_id.code

        employee_stripe_id = employee_sudo.private_stripe_id
        if employee_stripe_id:
            success_message = _("The Cardholder had been successfully updated.")
            route = 'cardholders/{cardholder_id}'
            route_params = {'cardholder_id': employee_stripe_id}
            del payload['name']
        else:
            route = 'cardholders'
            route_params = {}
            success_message = _("The Cardholder had been successfully created.")

        payload = {key: value for key, value in payload.items() if value is not False}  # Else Stripe consider it a value
        response = make_request_stripe_proxy(self.company_id.sudo(), route, route_params, payload=payload, method='POST')

        if not employee_stripe_id:
            employee_sudo.private_stripe_id = response['id']
            employee_sudo.flush_recordset(('private_stripe_id',))
        self.env.cr.precommit.add(self._transfer_messages_to_card)
        self.env.user._bus_send('simple_notification', {
            'type': 'success',
            'message': success_message,
        })
        # What if we need to request terms of services approvals (US-case TBDL)?

        if self.env.context.get('stripe_card_action_activate'):
            if not self.env.context.get('test_no_commit'):
                self.env.cr.commit()
            return self.card_id.action_activate_card()

        return {'type': 'ir.actions.act_window_close'}

    def _transfer_messages_to_card(self):
        """ Copy the messages created for the wizard to all the cardholder cards """
        create_vals = []
        subtype = self.env.ref('hr_expense_stripe.mt_stripe_cardholder_updated', raise_if_not_found=False)
        common_vals = {
            'model': 'hr.expense.stripe.card',
            'author_id': self.env.user.partner_id.id,
        }
        if subtype:
            common_vals['subtype_id'] = subtype.id
        messages_to_unlink = self.env['mail.message']
        for wizard in self:
            # Get the cardholder cards that belong to the same company
            cardholder_user_su = wizard.sudo().employee_id.user_id
            cards_su = cardholder_user_su.stripe_card_ids.filtered(lambda card: card.company_id == wizard.company_id)
            message = max(wizard.sudo().message_ids, key=lambda msg: msg.date, default=None)  # Only the last message
            if message:
                for card_su in cards_su:
                    create_vals += message.copy_data({
                        **common_vals,
                        'res_id': card_su.id,
                    })
                messages_to_unlink += message

        if create_vals:
            self.env['mail.message'].create(create_vals)
        if messages_to_unlink:
            messages_to_unlink.unlink()
