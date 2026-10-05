# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, Command, models, _

from odoo.addons.account.models.chart_template import template, TAX_TAG_DELIMITER


_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)
        if self.env.context.get('chart_template_load'):
            self._load_payroll_accounts(template_code, company)

    def _load_payroll_accounts(self, template_code, companies):
        config_method = getattr(self, f'_configure_payroll_account_{template_code}', None)
        if config_method:
            config_method(companies)

    @api.model
    def _configure_payroll_account(self, companies, country_code, account_codes=None, account_refs=None, rules_mapping=None, default_account=None):
        # companies: Recordset of the companies to configure
        # country_code: country code to find payroll structures and tax tags
        # account_codes: list of account codes to look up by prefix (alternative to account_refs)
        # account_refs: list of XML IDs to look up (alternative to account_codes)
        # rules_mapping: dictionary of the debit/credit accounts and tax tags for each related rule
        # default_account: default account to specify on the created journals
        structures = self.env['hr.payroll.structure'].search([('country_id.code', '=', country_code)])
        AccountAccount = self.env['account.account']
        rule_tag_mapper = self._get_tag_mapper(self.env['res.country'].search([('code', '=', country_code)]).id)
        if not companies or not structures:
            return
        for company in companies:
            self = self.with_company(company)

            # Enable SEPA batch payment by default for some countries
            if company.country_id.code in ['BE', 'CH']:
                company.batch_payroll_move_lines = True
            accounts = {}
            if account_codes:
                for code in account_codes:
                    account = AccountAccount.with_company(company).search([
                        *AccountAccount._check_company_domain(company),
                        ('code', '=like', '%s%%' % code)], limit=1)
                    if not account:
                        _logger.warning("Payroll configuration: Missing account %s", code)
                    accounts[code] = account
            elif account_refs:
                for xml_id in account_refs:
                    account = self.ref(xml_id, raise_if_not_found=False) or AccountAccount
                    if not account:
                        _logger.warning("Payroll configuration: Missing account %s", xml_id)
                    accounts[xml_id] = account

            journal = self.ref('hr_payroll_account_journal')
            if not journal.default_account_id and default_account:
                journal.default_account_id = accounts[default_account].id
            structures.with_company(company).journal_id = journal

            for rule, rule_mapping in rules_mapping.items():
                vals = {}
                if 'credit' in rule_mapping:
                    vals['account_credit'] = accounts.get(rule_mapping['credit'], AccountAccount).id
                if 'debit' in rule_mapping:
                    vals['account_debit'] = accounts.get(rule_mapping['debit'], AccountAccount).id
                if 'debit_tags' in rule_mapping:
                    vals['debit_tag_ids'] = [Command.set(rule_tag_mapper(*rule_mapping['debit_tags'].split(TAX_TAG_DELIMITER)))]
                if 'credit_tags' in rule_mapping:
                    vals['credit_tag_ids'] = [Command.set(rule_tag_mapper(*rule_mapping['credit_tags'].split(TAX_TAG_DELIMITER)))]
                if vals:
                    rule.with_company(company).write(vals)

    @template(model='account.journal')
    def _get_payroll_account_journal(self, template_code):
        return {
            'hr_payroll_account_journal': {
                'name': _("Salaries"),
                'code': _("SLR"),
                'type': 'general',
                'sequence': 99,
            },
        }

    @template(model='hr.payroll.structure')
    def _get_payroll_structure(self, template_code):
        return {
            structure.id: {
                'journal_id': 'hr_payroll_account_journal',
            }
            for structure in self.env['hr.payroll.structure'].sudo().with_context(active_test=False).search([])
        }
