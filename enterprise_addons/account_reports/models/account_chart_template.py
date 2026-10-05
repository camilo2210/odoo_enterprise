from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _pre_reload_data(self, company, template_data, data, force_create=True, force_update=False):
        # EXTENDS account
        super()._pre_reload_data(company, template_data, data, force_create=force_create, force_update=force_update)
        if force_update:
            return

        # A return type is a single record shared by every company, so the accounts it settles on are
        # configuration rather than master data. Reloading the chart must not undo them.
        for xmlid, values in data.get('account.return.type', {}).items():
            return_type = self.ref(xmlid, raise_if_not_found=False)
            if not return_type:
                continue
            for field_name in ('advance_tax_payment_account_id', 'tax_payable_account_id', 'tax_receivable_account_id'):
                if field_name in values and return_type.with_company(company)[field_name]:
                    del values[field_name]

    def _instantiate_foreign_taxes(self, country, company):
        # EXTENDS account
        res = super()._instantiate_foreign_taxes(country, company)
        self._setup_foreign_closing_accounts(country, company)
        return res

    def _setup_foreign_closing_accounts(self, country, company):
        """ Give the returns of a foreign VAT registration their own settlement accounts."""
        foreign_return_types = self.env['account.return.type'].sudo().search([
            ('country_id', '=', country.id),
        ]).filtered('is_tax_return_type')
        domestic_return_type = self.env['account.return.type'].sudo().search([
            ('country_id', '=', company.account_fiscal_country_id.id),
        ]).filtered('is_tax_return_type')[:1]
        if not foreign_return_types or not domestic_return_type:
            return

        field_and_names = (
            ('tax_payable_account_id', self.env._("Foreign tax account payable (%s)", country.code)),
            ('tax_receivable_account_id', self.env._("Foreign tax account receivable (%s)", country.code)),
            ('advance_tax_payment_account_id', self.env._("Foreign advance tax payment account (%s)", country.code)),
        )
        for field_name, account_name in field_and_names:
            if any(foreign_return_types.with_company(company).mapped(field_name)):
                continue
            domestic_account = domestic_return_type.with_company(company)[field_name]
            if not domestic_account:
                continue
            foreign_return_types.with_company(company)[field_name] = self._create_foreign_account(company, domestic_account, account_name)

    @template(model='account.journal')
    def _get_account_reports_journal(self, template_code):
        """Add a journal for the tax returns."""
        return {
            'tax_returns': {
                'name': self.env._("Tax Returns"),
                'type': 'general',
                'code': 'TAX',
                'show_on_dashboard': False,
            },
        }

    @template(model='res.company')
    def _get_account_reports_res_company(self, chart_template):
        """Make sure the tax return journal is set on the company.

        This is necessary when the CoA was already installed before this module.
        The method is called in the post-init hook of this module.
        """
        company = self.env.company
        return {
            company.id: {
                'account_tax_return_journal_id': company.account_tax_return_journal_id.id or 'tax_returns',
            },
        }

    @template(model='account.return.type')
    def _instantiate_returns_on_loading(self, chart_template):
        # Make sure all appropriate returns are directly generated when installing a CoA
        self.env['account.return.type'].sudo()._generate_or_refresh_all_returns(self.env.company.root_id)
