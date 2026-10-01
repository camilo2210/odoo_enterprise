from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


SSO_ACCOUNT_FIELDS = [
    'address_street_name',
    'address_street_name2',
    'address_city',
    'address_zip',
    'address_country_code',
    'subscriber_title',
    'subscriber_name',
    'subscriber_email',
    'subscriber_phone',
    'subscriber_firstname',
    'technical_contact_name',
    'technical_contact_phone',
    'technical_contact_email',
    'gdpr_contact_email',
    'gdpr_contact_firstname',
    'gdpr_contact_function',
    'gdpr_contact_name',
    'gdpr_contact_phone',
]


class L10nFrASPOneSSOWizard(models.TransientModel):
    _name = 'l10n_fr_reports.aspone.sso.wizard'
    _description = "ASPOne Single Sign-On Wizard"

    company_id = fields.Many2one('res.company')
    siren = fields.Char(compute='_compute_siren', readonly=True)
    nic = fields.Char(compute='_compute_siren', readonly=True)
    admin_id = fields.Many2one('res.users', compute='_compute_admin')
    address_street_name = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    address_street_name2 = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    address_city = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    address_zip = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    address_country_code = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=2)
    subscriber_title = fields.Selection([('MS', 'Ms./Mrs.'), ('MR', 'Mr')])
    subscriber_firstname = fields.Char(size=35)
    subscriber_name = fields.Char(size=35)
    subscriber_email = fields.Char(compute='_compute_user_info', store=True, readonly=False)
    subscriber_phone = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=15)
    technical_contact_name = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    technical_contact_phone = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    technical_contact_email = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    gdpr_contact_firstname = fields.Char(size=35)
    gdpr_contact_name = fields.Char(size=35)
    gdpr_contact_function = fields.Char(size=35, default="Account manager")
    gdpr_contact_email = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)
    gdpr_contact_phone = fields.Char(compute='_compute_user_info', store=True, readonly=False, size=35)

    @api.depends('company_id')
    def _compute_siren(self):
        for wizard in self:
            wizard.siren = wizard.company_id.partner_id.l10n_fr_siret[:9]
            wizard.nic = wizard.company_id.partner_id.l10n_fr_siret[9:14]

    @api.depends('admin_id')
    def _compute_user_info(self):
        def get_str(key):
            if not wizard.admin_id[key]:
                return ''
            return wizard.admin_id[key][:35]
        for wizard in self:
            wizard.address_street_name = get_str('street')
            wizard.address_street_name2 = get_str('street2')
            wizard.address_city = get_str('city')
            wizard.address_zip = get_str('zip')
            wizard.address_country_code = get_str('country_code')
            wizard.subscriber_email = get_str('email')
            wizard.subscriber_phone = get_str('phone')
            wizard.technical_contact_name = get_str('name')
            wizard.technical_contact_phone = get_str('phone')
            wizard.technical_contact_email = get_str('email')
            wizard.gdpr_contact_email = get_str('email')
            wizard.gdpr_contact_phone = get_str('phone')

    @api.depends('company_id')
    def _compute_admin(self):
        # try to find an admin with the info we need
        admins_per_companies = dict(self.env['res.users'].read_group(
            domain=Domain.AND([
                [('role', '=', 'group_system'), ('company_ids', 'in', self.company_id.ids)],
                [(field, '!=', False) for field in (
                    'name', 'street', 'city', 'zip', 'country_code', 'email', 'phone',
                )],
            ]),
            groupby=['company_ids'],
            aggregates=['id:array_agg'],
        ))
        missing_company_ids = set(self.company_id.ids) - set(admins_per_companies)
        if missing_company_ids:
            # if no admin with all the info, find any admin
            admins_per_companies = {
                **admins_per_companies,
                **dict(self.env['res.users'].read_group(
                    domain=[('role', '=', 'group_system'), ('company_ids', 'in', missing_company_ids)],
                    groupby=['company_ids'],
                    aggregates=['id:array_agg'],
                )),
            }
        for wizard in self:
            company_admins = admins_per_companies.get(wizard.company_id.id)
            wizard.admin_id = company_admins[0] if company_admins else False

    def _make_request(self, endpoint, company, params=None):
        if not company.partner_id.l10n_fr_siret:
            raise UserError(self.env._('Company must have SIRET set.'))
        base_url = self.env['account.report.async.document']._get_aspone_endpoint()
        return self.env['account.report.async.document']._get_fr_webservice_answer(
            url=base_url + endpoint,
            params={
                'db_uuid': self.env['ir.config_parameter'].sudo().get_str('database.uuid'),
                'debtor_identifier': company.partner_id.l10n_fr_siret[:14],
                **(params if params else {}),
            },
        )

    @api.model
    def _open_sso_url(self, res):
        if not res['status'] == 'sso_url':
            raise UserError(self.env._('Could not get Single Sign-On URL.'))
        return {
            'type': 'ir.actions.act_url',
            'url': res['url'],
            'target': 'new',
            'close': True,
        }

    def create_sso_account(self):
        """ Call IAP with data to create a SSO secondary account
        """
        params = {'account_data': {field: self[field] for field in SSO_ACCOUNT_FIELDS}}
        res = self._make_request(
            '/api/l10n_fr_aspone/1/get_sso_url',
            self.company_id,
            params,
        )
        return self._open_sso_url(res)

    @api.model
    def _action_redirect(self, company):
        """ Get sso link, if needed create secondary acount
        """
        res = self._make_request(
            '/api/l10n_fr_aspone/1/get_sso_url',
            company,
        )
        if res['status'] == 'send_data':  # secondary acount does not exists, create one
            wizard = self.create({'company_id': company.id})
            return wizard._get_records_action(
                name=self.env._("Single Sign-On ASPOne Account Creation"),
                target='new',
            )
        return self._open_sso_url(res)

    @api.model
    def get_fiscal_report_action(self, company_id):
        company = self.env["res.company"].browse(company_id)
        if company.country_id.code in company._get_france_country_codes() and company.l10n_fr_fiscal_regime == 'normal':
            return self._action_redirect(company)
        else:
            return self.env.ref('l10n_fr_reports.action_account_report_l10n_fr_fiscal_declaration').read()[0]
