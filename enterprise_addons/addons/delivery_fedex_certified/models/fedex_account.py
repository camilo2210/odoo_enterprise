from datetime import datetime, timedelta

from odoo import api, fields, models

TOKEN_EXPIRATION_TOLERANCE = 30  # seconds


class FedexAccount(models.Model):
    """
    FedexAccount model for managing Fedex shipping account credentials.

    This model stores FedEx account authentication details including account number,
    API credentials, and authorization tokens. The child_key and child_secret are
    specific to each account_number and are only usable with Odoo as the integrator.

    Attributes:
        account_number (str): Unique FedEx account identifier.
        child_key (str): FedEx API key specific to this account_number, valid only with Odoo integration.
        child_secret (str): FedEx API secret specific to this account_number, valid only with Odoo integration.
        auth_token (str): Current OAuth authorization token for FedEx API requests.
        auth_token_expiration (datetime): Expiration timestamp of the authorization token.
    """
    _name = 'fedex.certified.account'
    _description = 'Fedex Account'

    account_number = fields.Char(string='Account Number', required=True, readonly=True)
    child_key = fields.Char(string='Child Key', required=True, groups="base.group_system", readonly=True)
    child_secret = fields.Char(string='Child Secret', required=True, groups="base.group_system", readonly=True)
    auth_token = fields.Char(string='Authorization Token', groups="base.group_system", readonly=True)
    auth_token_expiration = fields.Datetime(string='Authorization Token Expiration', groups="base.group_system", readonly=True)

    test_account = fields.Boolean(string="Test Account", readonly=True)
    company_ids = fields.Many2many(comodel_name='res.company', string="Allowed Companies", help="Leaving this field empty allows all companies.")
    name = fields.Char(string='Name', compute='_compute_name')
    user_id = fields.Many2one('res.users', string="FedEx EULA signatory", readonly=True)
    sign_date = fields.Datetime(string='EULA signing date', readonly=True)
    eula_read = fields.Boolean(string="I acknowledge the reading of the FedEx End User License Agreement", readonly=True, default=False)
    eula_accepted = fields.Boolean(string="I accept the terms of FedEx EULA to start shipping", readonly=True, default=False)

    @api.depends('account_number')
    def _compute_name(self):
        for record in self:
            record.name = f"FedEx Account {record.account_number}"

    def _get_valid_token(self):
        """
        Returns a valid authorization token for the FedEx API. If the current token is expired or not set, it returns None.
        """
        if self.auth_token and self.auth_token_expiration and fields.Datetime.now() < self.auth_token_expiration:
            return self.auth_token
        else:
            return None

    def _is_eula_agreed(self):
        return self.eula_read and self.eula_accepted

    def _set_token(self, token, duration):
        self.auth_token = token
        self.auth_token_expiration = datetime.now() + timedelta(seconds=duration - TOKEN_EXPIRATION_TOLERANCE)
