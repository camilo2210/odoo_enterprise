# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    voes = fields.Char(string="VOES Number", help="Used for companies outside EU that want to make use of OSS")
    ioss = fields.Char(string="IOSS Number", help="Identification number for companies that import goods and services into the EU. For use in OSS reports.")
    intermediary_no = fields.Char(string="Intermediary Number", help="Used for companies outside EU that import into the EU via an intermediary for OSS taxes")

    def _map_eu_taxes(self):
        super()._map_eu_taxes()
        self.env['account.return.type']._generate_or_refresh_all_returns(self.root_id)
        self._setup_oss_closing_accounts()

    def _setup_oss_closing_accounts(self):
        """ Give the OSS returns their own settlement accounts."""
        oss_return_types = self.env['account.return.type']
        for xml_id in ('l10n_eu_oss_reports.eu_oss_sales_tax_return_type', 'l10n_eu_oss_reports.eu_oss_imports_tax_return_type'):
            oss_return_types |= self.env.ref(xml_id, raise_if_not_found=False)
        if not oss_return_types:
            return

        for company in self:
            company = company.parent_ids.filtered('vat')[-1:] or company.root_id
            domestic_return_type = self.env['account.return.type'].sudo().search([
                ('country_id', '=', company.account_fiscal_country_id.id),
            ]).filtered(lambda rt: rt.is_tax_return_type and rt.with_company(company).tax_payable_account_id)[:1]
            if not domestic_return_type:
                continue

            for field_name in ('tax_payable_account_id', 'tax_receivable_account_id'):
                if any(oss_return_types.with_company(company).mapped(field_name)):
                    continue
                domestic_account = domestic_return_type.with_company(company)[field_name]
                if not domestic_account:
                    continue
                oss_account = self.env['account.account'].sudo().create({
                    'name': f'{domestic_account.name} OSS',
                    'code': self.env['account.account'].sudo()._search_new_account_code(domestic_account.with_company(company).code),
                    'account_type': domestic_account.account_type,
                    'reconcile': domestic_account.reconcile,
                    'non_trade': domestic_account.non_trade,
                    'company_ids': [Command.link(company.root_id.id)],
                })
                oss_return_types.with_company(company)[field_name] = oss_account

    def _get_available_tax_units(self, report, limit=None):
        self.ensure_one()
        if report.availability_condition == 'oss':
            return self.env['account.tax.unit'].search([
                ('company_ids', 'in', self.id),
                ('country_id', '=', self.account_fiscal_country_id.id),
            ], limit=limit)

        return super()._get_available_tax_units(report, limit=limit)
