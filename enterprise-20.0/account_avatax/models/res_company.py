import logging

from markupsafe import escape

from odoo import fields, models
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import format_list

from odoo.addons.account_avatax.lib.avatax_client import AvataxClient

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    avalara_api_id = fields.Char(string='Avalara API ID', groups='base.group_system')
    avalara_api_key = fields.Char(string='Avalara API KEY', groups='base.group_system')
    avalara_environment = fields.Selection(
        string="Avalara Environment",
        selection=[
            ('sandbox', 'Sandbox'),
            ('production', 'Production'),
        ],
        required=True,
        default='sandbox',
    )
    avalara_commit = fields.Boolean(string="Commit in Avatax")
    avalara_address_validation = fields.Boolean(string="Avalara Address Validation")
    avalara_use_upc = fields.Boolean(string="Use UPC", default=True)
    avalara_connection_method = fields.Selection(
        string="Avalara Connection Type",
        selection=[
            ('iap', 'Avalara Included'),
            ('manual', 'Avalara Direct'),
        ],
        required=True,
        default='iap',
        groups='base.group_system',
    )
    avalara_iap_connected = fields.Boolean(string="Is connected to IAP", readonly=True, groups='base.group_system')
    avalara_account_email = fields.Char(string="Avalara Master Email", groups='base.group_system')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    avalara_api_id = fields.Char(
        related='company_id.avalara_api_id',
        readonly=False,
        string='Avalara API ID',
    )
    avalara_api_key = fields.Char(
        related='company_id.avalara_api_key',
        readonly=False,
        string='Avalara API KEY',
    )
    avalara_partner_code = fields.Char(
        related='company_id.partner_id.avalara_partner_code',
        readonly=False,
        string='Avalara Company Code',
        help="The Avalara Company Code for this company. Avalara will interpret as DEFAULT if it"
             " is not set.",
    )
    avalara_environment = fields.Selection(
        related='company_id.avalara_environment',
        readonly=False,
        string="Avalara Environment",
        required=True,
    )
    avalara_commit = fields.Boolean(
        related='company_id.avalara_commit',
        readonly=False,
        string='Commit in Avatax',
        help="The transactions will be committed for reporting in Avatax.",
    )
    avalara_address_validation = fields.Boolean(
        related='company_id.avalara_address_validation',
        string='Avalara Address Validation',
        readonly=False,
        help="Validate and correct the addresses of partners in North America with Avalara.",
    )
    avalara_use_upc = fields.Boolean(
        related='company_id.avalara_use_upc',
        readonly=False,
        string="Use UPC",
        help="Use Universal Product Code instead of custom defined codes in Avalara.",
    )
    avalara_connection_method = fields.Selection(
        related='company_id.avalara_connection_method',
        readonly=False,
        string='Avalara Integration Method',
    )
    avalara_iap_connected = fields.Boolean(
        related='company_id.avalara_iap_connected',
    )
    avalara_account_email = fields.Char(
        related='company_id.avalara_account_email',
        readonly=False,
    )

    def avatax_sync_company_params(self):
        """Sync all the (supported) parameters that can be configured in Avatax."""
        def get_countries(code_list):
            uncached = set(code_list) - set(country_cache)
            if uncached:
                country_cache.update({
                    country.code: country.id
                    for country in self.env['res.country'].search([('code', 'in', tuple(uncached))])
                })
            return self.env['res.country'].browse([country_cache[code] for code in code_list if country_cache[code]])
        country_cache = {'*': False}

        # Fetch and create the exemption codes
        existing = {
            exempt['code'] for exempt in self.env['avatax.exemption'].search_read(
                domain=[('company_id', '=', self.company_id.id)],
                fields=['code'],
            )
        }
        client = AvataxClient._get_client(self.company_id)
        response = client.list_entity_use_codes()
        error = self.env['account.external.tax.mixin']._handle_response(response, self.env._(
            "Odoo could not fetch the exemption codes of %(company)s",
            company=self.company_id.display_name,
        ))
        if error:
            raise UserError(error)
        self.env['avatax.exemption'].create([
            {
                'code': vals['code'],
                'description': vals['description'],
                'name': vals['name'],
                'valid_country_ids': [(6, 0, get_countries(vals['validCountries']).ids)],
                'company_id': self.company_id.id,
            }
            for vals in response['value']
            if vals['code'] not in existing
        ])

        self._avatax_sync_uoms(client)
        self._avatax_sync_parameters(client)
        return True

    def _avatax_sync_uoms(self, client):
        response = client.list_unit_of_measurements()
        error = self.env['account.external.tax.mixin']._handle_response(response, self.env._(
            "Odoo could not fetch the units of measurement of %(company)s",
            company=self.company_id.display_name,
        ))
        if error:
            raise UserError(error)

        existing = {
            uom.code: uom
            for uom in self.env['avatax.uom'].search([('company_id', '=', self.company_id.id)])
        }
        to_create = []
        for vals in response['value']:
            uom_vals = {
                'name': vals['shortDesc'],
                'code': vals['code'],
                'measurement_type': vals.get('measurementTypeCode', ''),
            }
            if uom := existing.get(vals['code']):
                uom.write(uom_vals)
            else:
                to_create.append({**uom_vals, 'company_id': self.company_id.id})
        self.env['avatax.uom'].create(to_create)

    def _avatax_sync_parameters(self, client):
        response = client.list_parameters()
        error = self.env['account.external.tax.mixin']._handle_response(response, self.env._(
            "Odoo could not fetch the parameters of %(company)s",
            company=self.company_id.display_name,
        ))
        if error:
            raise UserError(error)

        product_params = {
            vals['name']: vals for vals in response['value']
            if vals.get('attributeType') == 'Product'
        }
        existing = {
            param.technical_name: param
            for param in self.env['avatax.parameter'].search([('company_id', '=', self.company_id.id)])
        }
        to_create = []
        for technical_name, vals in product_params.items():
            param_vals = {
                'technical_name': technical_name,
                'name': vals.get('label'),
                'description': vals.get('helpText'),
                'scope': 'Product',
                'data_type': vals.get('dataType'),
                'measurement_type': vals.get('measurementType'),
            }
            if param := existing.get(technical_name):
                param.write(param_vals)
            else:
                to_create.append({**param_vals, 'company_id': self.company_id.id})

        new_params = self.env['avatax.parameter'].create(to_create)
        for param in new_params:
            existing[param.technical_name] = param

        for param in existing.values():
            api_vals = product_params.get(param.technical_name, {})
            api_selections = set(api_vals.get('values', []))
            existing_selections = set(param.selection_ids.mapped('name'))
            if to_add := api_selections - existing_selections:
                self.env['avatax.parameter.selection'].create([
                    {'parameter_id': param.id, 'name': val} for val in to_add
                ])

    def avatax_ping(self):
        """Test the connection and the credentials. Ping avalara and pull all nexus locations as well."""
        client = AvataxClient._get_client(self.company_id)
        query_result = client.ping()

        nexus_html = ""
        company_result = client.get_companies()
        if company_result.get('value'):
            company_id = company_result['value'][0]['id']
            nexus_result = client.list_nexus(company_id)
            nexus_html = self._format_nexus(nexus_result.get('value') or [])

        return self._create_avatax_popup(
            self.env._("Test Result"),
            self._format_response(query_result) + nexus_html,
        )

    def avatax_migrate_to_iap(self):
        """Migrate an existing Avalara Direct account to Avalara Included (IAP)."""
        ProxyUser = self.env['account_edi_proxy_client.user']
        response = ProxyUser._register_avatax_proxy_user(self.company_id, 'link_to_iap', {
            'avalara_api_id': self.company_id.sudo().avalara_api_id,
            'client_secret': self.company_id.sudo().avalara_api_key or '',
        })
        return self._create_avatax_popup(
            self.env._("Successfully migrated to Avalara Included"),
            self._format_response(response),
        )

    def avatax_connect_to_iap(self):
        """Create a new Avalara account and connect to IAP."""
        if not self.avalara_account_email:
            raise ValidationError(self.env._("Please specify the contact email for the Avatax Account."))

        partner = self.company_id.partner_id
        required_address_fields = ("street", "city", "state_id", "country_id", "zip")
        for field in required_address_fields:
            if not partner[field]:
                raise RedirectWarning(
                    self.env._("Please set a complete address on your company."),
                    partner._get_records_action(),
                    self.env._("Go to company configuration"),
                )

        main_user = self.env.user
        name_parts = main_user.name.split()
        first_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else name_parts[0]
        last_name = name_parts[-1] if len(name_parts) > 1 else ""
        ProxyUser = self.env['account_edi_proxy_client.user']
        response = ProxyUser._register_avatax_proxy_user(self.company_id, 'connect_to_iap', {
            'json': {
                "accountName": self.company_name,
                "website": self.company_id.website or '',
                "firstName": first_name,
                "lastName": last_name,
                "email": self.avalara_account_email,
                "companyCode": 'DEFAULT',
                "companyAddress": {
                    "line": self.company_id.street or '',
                    "city": self.company_id.city or '',
                    "region": self.company_id.state_id.code or '',
                    "country": self.company_id.country_code or '',
                    "postalCode": self.company_id.zip or '',
                },
                "acceptAvalaraTermsAndConditions": True,
                "haveReadAvalaraTermsAndConditions": True,
            },
        })

        self.company_id.avalara_api_id = response['Avalara Account #']

        return self._create_avatax_popup(
            self.env._("Successfully created an Avalara Account"),
            self._format_response(response),
        )

    def _format_response(self, query_result):
        if not query_result:
            return ""
        html_content = self.env._("Authentication success.") if query_result.get('authenticated') else self.env._("Authentication failed.")

        html_content += '<ul>'
        for key, value in query_result.items():
            if isinstance(value, list):
                value = format_list(self.env, value, style='standard', lang_code='en_US')
            html_content += f'<li><span class="fw-bold">{escape(key.capitalize())}:</span> {escape(str(value))}</li>'
        html_content += '</ul>'
        return html_content

    def _format_nexus(self, nexus_values):
        """Render the nexus locations grouped by country.

        Avalara returns one row per jurisdiction (state, county, city, special
        district) plus a country-wide row, so the raw list is full of duplicates
        and mixes countries with their regions. Group by country, drop the
        country-wide rows, and dedupe/sort the regions.
        """
        by_country = {}
        for nexus in nexus_values:
            juris_type = nexus.get('jurisdictionTypeId')
            juris_type_legacy = nexus.get('jurisTypeId')
            if not (juris_type or juris_type_legacy):
                continue
            if juris_type == 'Country' or juris_type_legacy == 'CNT':
                continue  # country-wide nexus, not a distinct jurisdiction
            region_name = nexus.get('jurisName')
            country = nexus.get('country')
            if not region_name or not country:
                continue
            by_country.setdefault(country, set()).add(region_name.title())
        if not by_country:
            return ""

        country_names = {
            country.code: country.name
            for country in self.env['res.country'].search([('code', 'in', list(by_country))])
        }
        total = sum(len(regions) for regions in by_country.values())
        summary = self.env._(
            "%(jurisdictions)s jurisdictions across %(countries)s countries",
            jurisdictions=total,
            countries=len(by_country),
        )

        html_content = (
            f'<div class="fw-bold mt-3">{escape(self.env._("Nexus locations"))}</div>'
            f'<div class="text-muted small mb-2">{escape(summary)}</div>'
        )
        for code, regions in sorted(by_country.items(), key=lambda item: country_names.get(item[0]) or item[0]):
            name = country_names.get(code) or code
            html_content += (
                f'<div class="fw-bold mt-2">{escape(name)} ({len(regions)})</div>'
                f'<div>{escape(" · ".join(sorted(regions)))}</div>'
            )
        return html_content

    def _create_avatax_popup(self, title, body):
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'res_model': 'avatax.connection.test.result',
            'res_id': self.env['avatax.connection.test.result'].create({'server_response': body}).id,
            'target': 'new',
            'views': [(False, 'form')],
        }

    def avatax_log(self):
        self.env['account.external.tax.mixin']._enable_external_tax_logging('account_avatax.log.end.date')
        return True
