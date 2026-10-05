from odoo import fields, models, _
from odoo.exceptions import ValidationError

from ..models.fedex_request import FedexRequest, FEDEX_CURR_MATCH

STATE_VIEW_MAPPING = {
    'eula': ('eula', 'EULA'),
    'address': ('address', 'Shipper Information'),
    'options': ('validation_options', 'Validation Options'),
    'invoice': ('invoice', 'Invoice Validation'),
    'pin_generation': ('pin_generation', 'PIN Generation'),
    'pin': ('pin_validation', 'PIN Validation'),
    'success': ('success', 'Success'),
    'error': ('error', 'Error'),
}


class FedexAccountRegistrationWizard(models.TransientModel):
    _name = 'fedex.certified.account.registration.wizard'
    _description = "FedEx Account Registration Wizard"

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    fedex_carrier_id = fields.Many2one('delivery.carrier', string="FedEx Carrier", required=True, readonly=True, domain="[('delivery_type', '=', 'fedex_certified')]")

    account_auth_token = fields.Char(string="Account Authentication Token", readonly=True, default=None)
    state = fields.Char(string="State", default='eula', readonly=True)  # eula -> address -> options -> [ invoice | (pin_generation -> pin)]* -> success, *error
    error_message = fields.Text(string="Error Message", readonly=True)
    warning_message = fields.Text(string="Warning Message", readonly=True)

    fedex_account_id = fields.Many2one('fedex.certified.account')

    # EULA fields
    is_eula_scrolled = fields.Boolean(default=False)
    eula_read = fields.Boolean(string="I acknowledge the reading of the FedEx End User License Agreement")
    eula_accepted = fields.Boolean(string="I accept the terms of FedEx EULA to start shipping")
    eula_datetime = fields.Datetime()

    # Adress validation fields
    account_number = fields.Char(string="FedEx Account Number")  # An object {key:..., value:...} Fedex-side. leave key empty.
    city = fields.Char(string="City")
    country_id = fields.Many2one('res.country', string="Country")
    customer_name = fields.Char(string="Customer Name")  # Max 50 chars
    postal_code = fields.Char(string="Postal Code")
    residential_address = fields.Boolean(string="Residential Address", default=False,
        help="Indicates whether the address is residential or commercial. This information is used by FedEx to determine the appropriate delivery options and rates.")
    street_line_1 = fields.Char(string="Street Line 1", help="Street line 1 of the address. Must be a string with a maximum of 35 characters.")
    street_line_2 = fields.Char(string="Street Line 2", help="Street line 2 of the address. Must be a string with a maximum of 35 characters.")
    state_or_province_code = fields.Char(string="State or Province Code", default="",
        help="State or province code of the address. Must be a valid code recognized by FedEx.")

    # MFA Choice fields
    validation_options = fields.Selection([
        ('invoice', 'Invoice Validation'),
        ('pin_generation', 'Secure Code Validation'),
    ], string="Validation Option", default='invoice')
    invoice_max_retry_reached = fields.Boolean(default=False)
    pin_max_retry_reached = fields.Boolean(default=False)
    invoice_failed_once = fields.Boolean(default=False)
    pin_failed_once = fields.Boolean(default=False)

    # Invoice validation fields
    currency_id = fields.Many2one('res.currency', string="Currency")
    invoice_amount = fields.Float(string="Invoice Amount")
    invoice_date = fields.Date(string="Invoice Date")
    invoice_number = fields.Char(string="Invoice Number")

    # PIN generation/validation fields
    pin_options = fields.Selection([
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('CALL', 'Voice Call'),
    ], string="PIN Options", default='EMAIL')
    secure_code_pin = fields.Char(string="6 digits secure code")

    def action_accept_eula(self):
        return self._action_open_view('address')

    def action_validate_address(self):
        self._find_account_number_registered()
        if self.fedex_account_id:
            # Account already in the DB — don't block, just warn and let the
            # user continue the MFA flow. `_save_credentials` will update the
            # existing record's child_key/child_secret instead of creating a
            # duplicate.
            self.warning_message = self.env._(
                "FedEx account %(account)s is already registered in this database. "
                "Continuing will refresh its credentials (child_key / child_secret) "
                "on the existing record.",
                account=self.account_number,
            )
            if self.env.user.has_group('base.group_multi_company'):
                self.warning_message += self.env._(
                    "\nIf the existing record is restricted to other companies, "
                    "add the current carrier's company to its `Allowed Companies` list."
                )
        self.eula_datetime = fields.Datetime.now()

        required = [self.account_number, self.customer_name, self.street_line_1, self.city, self.postal_code, self.country_id]
        required_tags = [_('FedEx Account Number'), _("Customer Name"), _("Street Line 1"), _("City"), _("Postal Code"), _("Country")]
        missing = [required_tags[i] for i, v in enumerate(required) if not v]
        if missing:
            raise ValidationError(_('Missing required field(s):\n\t- %s', '\n\t- '.join(missing)))

        data = {
            'address': {
                'residential': self.residential_address,
                'city': self.city,
                'countryCode': self.country_id.code,
                'postalCode': self.postal_code,
                'streetLines': [self.street_line_1, self.street_line_2] if self.street_line_2 else [self.street_line_1],
                'stateOrProvinceCode': self.state_or_province_code,
            },
            'accountNumber': {
                'key': '',
                'value': self.account_number,
            },
            'customerName': self.customer_name,
        }
        return self._process_request(data)

    def action_validate_invoice(self):
        required = [self.invoice_number, self.invoice_date, self.invoice_amount, self.currency_id]
        required_tags = [_('Invoice Number'), _("Invoice Date"), _("Invoice Amount"), _("Currency")]
        missing = [required_tags[i] for i, v in enumerate(required) if not v]
        if missing:
            raise ValidationError(_('Missing required field(s):\n\t- %s', '\n\t- '.join(missing)))

        data = {
            'invoiceDetail': {
                'number': self.invoice_number,
                'amount': f"{self.invoice_amount:.2f}",
                'currency': FEDEX_CURR_MATCH.get(self.currency_id.name, self.currency_id.name),
                'date': self.invoice_date.strftime('%Y-%m-%d'),
            }
        }
        return self._process_request(data)

    def action_validate_pin(self):
        if not self.secure_code_pin:
            raise ValidationError(_('PIN is required for PIN Validation'))
        data = {
            'secureCodePin': self.secure_code_pin,
        }
        return self._process_request(data)

    def action_choose_validation_factor(self):
        return self._action_open_view(self.validation_options)

    def action_back_to_options(self):
        return self._action_open_view('options')

    def action_choose_pin_generation(self):
        data = {'option': self.pin_options}
        return self._process_request(data)

    def action_open_account_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fedex.certified.account',
            'res_id': self.fedex_account_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _process_request(self, data):
        fedex_request = FedexRequest(self.fedex_carrier_id)
        try:
            response = fedex_request._account_registration(self.state, data, self.account_auth_token)
        except ValidationError as e:
            self.error_message = str(e)
            self._track_failure()
            if 'MAXIMUM.ATTEMPTS.REACHED' in str(e):
                self._set_max_retry_reached()
            if self.invoice_max_retry_reached or self.pin_max_retry_reached or (self.invoice_failed_once and self.pin_failed_once):
                return self._set_support_error_message()
            return self._action_open_view()

        if self.state == 'pin_generation':
            return self._action_open_view('pin')
        elif 'mfaOptions' in response:
            self.account_auth_token = response['mfaOptions'][0].get('accountAuthToken')
            return self._action_open_view('options')
        elif 'credentials' in response or 'child_Key' in response:
            self._save_credentials(response.get('credentials') or response)
            return self._action_open_view('success')

    def _action_open_view(self, new_state=None):
        if new_state is not None and new_state != self.state and new_state != 'error':
            self.state = new_state
            self.error_message = False

        view_id = self.env.ref(f'delivery_fedex_certified.view_fedex_account_registration_{STATE_VIEW_MAPPING[self.state][0]}_form').id
        name = f'FedEx Account Registration - {STATE_VIEW_MAPPING[self.state][1]}'
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'fedex.certified.account.registration.wizard',
            'res_id': self.id,
            'view_id': view_id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _find_account_number_registered(self):
        self.fedex_account_id = self.env['fedex.certified.account'].search([('account_number', '=', self.account_number)], limit=1)

    def _save_credentials(self, credentials):
        vals = {
            'account_number': self.account_number,
            'child_key': credentials['child_Key'],
            'child_secret': credentials['child_secret'],
            'user_id': self.env.user.id,
            'sign_date': self.eula_datetime,
            'eula_read': self.eula_read,
            'eula_accepted': self.eula_accepted,
            'test_account': not self.fedex_carrier_id.prod_environment,
        }
        # If a record for this account_number already exists, refresh its
        # credentials in place (the wizard set `fedex_account_id` from
        # `_find_account_number_registered` on the address step). Otherwise
        # create a new one. Either way the carrier ends up pointing at the
        # one canonical record for this account_number, so we never end up
        # with duplicates.
        if self.fedex_account_id:
            self.fedex_account_id.write(vals)
        else:
            self.fedex_account_id = self.env['fedex.certified.account'].create(vals)
        self.fedex_carrier_id.fedex_certified_account_id = self.fedex_account_id

    def _set_max_retry_reached(self):
        if self.state == 'invoice':
            self.invoice_max_retry_reached = True
        elif self.state in ('pin_generation', 'pin'):
            self.pin_max_retry_reached = True

    def _track_failure(self):
        if self.state == 'invoice':
            self.invoice_failed_once = True
        elif self.state in ('pin_generation', 'pin'):
            self.pin_failed_once = True

    def _set_support_error_message(self):
        self.error_message = _(
            "We are unable to process this request.\nPlease try again later or call FedEx Customer Service and ask for technical support.")
        return self._action_open_view('error')
