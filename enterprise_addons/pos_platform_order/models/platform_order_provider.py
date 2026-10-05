# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.fields import Domain
from odoo.exceptions import ValidationError


class PlatformOrderProvider(models.Model):
    _name = 'platform.order.provider'
    _description = 'Platform Order Provider'
    _order = 'module_state, state desc, sequence, name'
    _inherit = ['pos.load.mixin', 'image.mixin']
    _check_company_auto = True

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string="Sequence", help="Define the display order")
    code = fields.Selection(
        string="Code",
        help="The technical code of this platform order provider.",
        selection=[('none', "No Provider Set")],
        default='none',
        required=True,
    )
    state = fields.Selection(
        [('disabled', 'Disabled'), ('enabled', 'Enabled'), ('test', 'Test')],
        string='State', required=True, default='disabled', copy=False)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company)
    country_id = fields.Many2one(related='company_id.country_id', store=True, readonly=True)
    country_code = fields.Char(related='country_id.code', depends=['country_id'], readonly=True)

    # -- Default Configuration --
    default_payment_method_id = fields.Many2one(
        'pos.payment.method', string="Default Payment Method", copy=False,
        check_company=True, help="The default payment method to use for this provider.")
    default_pricelist_id = fields.Many2one(
        'product.pricelist', string="Default Price List", copy=False,
        check_company=True, help="The default price list to use for this provider.")

    # -- Technical Capabilities (Read-only) --
    support_combo = fields.Boolean(string="Supports Combo", readonly=True)
    valid_for_seconds = fields.Integer(string="Valid for (Seconds)", default=300, readonly=True)

    # -- Module Integration --
    module_id = fields.Many2one(string="Corresponding Module", comodel_name='ir.module.module')
    module_state = fields.Selection(string="Installation State", related='module_id.state')

    def button_immediate_install(self):
        """ Install the related module and set up default records. """
        self.ensure_one()
        if self.module_id:
            self.module_id.button_immediate_install()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def _check_required_if_provider(self):
        """ Check that provider-specific required fields have been filled.

        The fields that have the `required_if_provider='<provider_code>'` attribute are made
        required for all `payment.provider` records with the `code` field equal to `<provider_code>`
        and with the `state` field equal to `'enabled'` or `'test'`.

        Provider-specific views should make the form fields required under the same conditions.

        :return: None
        :raise ValidationError: If a provider-specific required field is empty.
        """
        field_names = []
        enabled_providers = self.filtered(lambda p: p.state in ['enabled', 'test'])
        for field_name, field in self._fields.items():
            required_for_provider_code = getattr(field, 'required_if_provider', None)
            if required_for_provider_code and any(
                required_for_provider_code == provider.code and not provider[field_name]
                for provider in enabled_providers
            ):
                ir_field = self.env['ir.model.fields']._get(self._name, field_name)
                field_names.append(ir_field.field_description)
        if field_names:
            raise ValidationError(
                self.env._("The following fields must be filled: %s", ", ".join(field_names))
            )

    def _valid_field_parameter(self, field, name):
        """ Allow 'required_if_provider' as a valid parameter on model fields. """
        return name == 'required_if_provider' or super()._valid_field_parameter(field, name)

    @api.model_create_multi
    def create(self, vals_list):
        providers = super().create(vals_list)
        providers._check_required_if_provider()
        return providers

    def write(self, vals):
        result = super().write(vals)
        self._check_required_if_provider()
        return result

    @api.model
    def _load_pos_data_domain(self, data):
        return [('state', '!=', 'disabled')]

    @api.model
    def _load_pos_data_fields(self, config_id):
        return ['id', 'name', 'code', 'write_date', 'valid_for_seconds']

    @api.model
    def _setup_provider(self, code):
        existing_providers = self.search(self._get_provider_domain(code), order='id')
        if not existing_providers:
            return  # No provider to set up.

        main_provider = existing_providers[:1]
        self._setup_payment_method(main_provider)
        self._setup_pricelist(main_provider)

        existing_provider_companies = existing_providers.company_id
        all_companies = self.env['res.company'].search(Domain('parent_id', '=', False))
        companies_needing_provider = all_companies.filtered_domain(Domain('id', 'not in', existing_provider_companies.ids))
        for company in companies_needing_provider:
            # Create a copy of the provider for each company.
            journal = self._setup_journal(company, code)
            payment_method = main_provider.default_payment_method_id.copy({'company_id': company.id, 'journal_id': journal.id})
            pricelist = main_provider.default_pricelist_id
            if pricelist.company_id.id not in {False, company.id} or pricelist.currency_id != company.currency_id:
                pricelist = pricelist.copy({'company_id': company.id, 'currency_id': company.currency_id.id})
            main_provider.copy({'company_id': company.id, 'default_payment_method_id': payment_method.id, 'default_pricelist_id': pricelist.id})

    @api.model
    def _setup_journal(self, company, code):
        providers_description = dict(self._fields['code']._description_selection(self.env) or [])
        journal_code = code.upper()
        if not (journal := self._get_provider_journal(journal_code, company.id)):
            journal = self.env['account.journal'].sudo().create({
                'name': providers_description[code],
                'code': journal_code,
                'type': 'bank',
                'company_id': company.id,
                'show_on_dashboard': False,
            })
        return journal

    @api.model
    def _setup_payment_method(self, provider):
        if provider.code != 'none':
            journal = self._setup_journal(provider.company_id, provider.code)
            providers_description = dict(self._fields['code']._description_selection(self.env) or [])
            if not (payment_method := self._get_provider_payment_method(provider.code, provider.company_id.ids)):
                payment_method = self.env['pos.payment.method'].create({
                    'name': providers_description[provider.code],
                    'type': 'bank',
                    'journal_id': journal.id,
                    'company_id': provider.company_id.id,
                })
            provider.default_payment_method_id = payment_method

    @api.model
    def _setup_pricelist(self, provider):
        if provider.code != 'none':
            if not (pricelist := self._get_provider_pricelist(provider.code, provider.company_id.ids)):
                providers_description = dict(self._fields['code']._description_selection(self.env) or [])
                pricelist = self.env['product.pricelist'].create({
                    'name': providers_description[provider.code],
                    'currency_id': provider.company_id.currency_id.id,
                    'company_id': False,
                })
            provider.default_pricelist_id = pricelist.id

    @api.model
    def _remove_provider(self, code):
        providers = self.search(self._get_provider_domain(code), order='id')

        payment_methods = self._get_provider_payment_method(code, providers.company_id.ids)
        journal = payment_methods.journal_id
        pricelist = self._get_provider_pricelist(code, providers.company_id.ids)

        providers.write(self._get_removal_values())
        main_provider = providers[:1]
        (providers - main_provider).unlink()

        payment_methods.unlink()
        journal.unlink()
        pricelist.unlink()

    @api.model
    def _get_provider_domain(self, code):
        return Domain('code', '=', code)

    @api.model
    def _get_provider_journal(self, code, company_id):
        return self.env['account.journal'].search(Domain.AND([Domain('code', '=', code), Domain('company_id', '=', company_id)]))

    @api.model
    def _get_provider_payment_method(self, code, company_ids):
        return self.env['pos.payment.method'].search(Domain.AND([Domain('journal_id.code', '=', code), Domain('company_id', 'in', company_ids)]))

    @api.model
    def _get_provider_pricelist(self, code, company_ids):
        name = dict(self._fields['code']._description_selection(self.env) or [])[code]
        return self.env['product.pricelist'].search(Domain.AND([Domain('name', '=', name), Domain('company_id', 'in', company_ids)]))

    def _get_removal_values(self):
        return {
            'code': 'none',
            'state': 'disabled',
        }
