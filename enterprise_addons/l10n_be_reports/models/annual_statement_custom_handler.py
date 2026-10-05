from dateutil.relativedelta import relativedelta
import json
import re

from lxml import etree

from odoo import fields, models, _
from odoo.fields import Domain
from odoo.exceptions import UserError, RedirectWarning
from odoo.tools.misc import get_lang


PREFIX = 'l10n_be_reports.'
REPORT_MATCHINGS = {
    ((f'{PREFIX}account_financial_report_bs_comp_acon', f'{PREFIX}account_financial_report_pl_comp_a'), f'{PREFIX}xbrl_template_acon'),
    ((f'{PREFIX}account_financial_report_bs_comp_acap', f'{PREFIX}account_financial_report_pl_comp_a'), f'{PREFIX}xbrl_template_acap'),
    ((f'{PREFIX}account_financial_report_bs_comp_fcon', f'{PREFIX}account_financial_report_pl_comp_f'), f'{PREFIX}xbrl_template_fcon'),
    ((f'{PREFIX}account_financial_report_bs_comp_fcap', f'{PREFIX}account_financial_report_pl_comp_f'), f'{PREFIX}xbrl_template_fcap'),
    ((f'{PREFIX}account_financial_report_bs_asso_a', f'{PREFIX}account_financial_report_pl_asso_a'), f'{PREFIX}xbrl_template_asso_a'),
    ((f'{PREFIX}account_financial_report_bs_asso_f', f'{PREFIX}account_financial_report_pl_asso_f'), f'{PREFIX}xbrl_template_asso_f'),
}


class AnnualStatementReportHandler(models.AbstractModel):
    _name = 'annual.statement.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Annual Statement Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if report.country_id.code == 'BE':
            options['buttons'].append({'name': "XBRL", 'sequence': 30, 'action': 'open_xbrl_wizard', 'file_export_type': 'XBRL'})

    def open_xbrl_wizard(self, options):
        return {
            'name': _('XBRL Export'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'l10n_be_reports.xbrl.export.wizard',
            'target': 'new',
            'context': {
                'options': options,
                },
            'views': [[False, 'form']],
        }

    def export_to_xbrl(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'generate_xbrl_file',
            }
        }

    def generate_xbrl_file(self, options):
        """This will generate the XBRL file (similar style to XML)."""

        report = self.env['account.report'].browse(options['report_id'])
        if report.country_id.code != 'BE':
            raise UserError(_("XBRL export is only applicable for Belgium reports. Please change to Belgium annual statement report."))

        last_deed_date = options.get('last_deed_date')

        current_fiscal_date = self.env.company.compute_fiscalyear_dates(fields.Date.to_date(options['date']['date_to']))
        options = report.get_options({
            **options,
            'date': {
                **options.get('date', {}),
                'date_from': current_fiscal_date['date_from'],
                'date_to': current_fiscal_date['date_to'],
            },
        })
        options['xbrl_current_fiscal_date'] = current_fiscal_date

        self._validate_company_data()

        # To extract house number: 2 capture groups, one for number, one for street
        match = re.findall(r'(\b\d+\w*\b)|((?:\b(?!\d)\w+\b(?:\s+|$))+)', self.env.company.street)
        house_number = next((m[0] for m in match if m[0]), None) or '0'
        street = next((m[1] for m in match if m[1]), None) or self.env.company.street

        data = {
            'company_lang': lang if (lang := get_lang(self.env).code.split('_')[0]) in ('fr', 'nl', 'de') else 'en',
            'company_registry': self.env.company.partner_id._get_preferred_legal_entity_identifier_vals().get('value', ''),  # will compute BCE from VAT if BCE is not set
            'date': fields.Date.context_today(self).strftime('%Y-%m-%d'),
            'date_from': current_fiscal_date['date_from'],
            'date_to': current_fiscal_date['date_to'],
            'company_type': "lgf:" + self.env.company.l10n_be_company_type_id.xbrl_code,
            'company_name': self.env.company.name,
            'company_street': street.strip(),
            'company_house_number': house_number,
            'company_postal_code': "pcd:m" + self.env.company.zip,
            'company_region': "cct:" + self.env.company.l10n_be_region_id.xbrl_code,
            'company_country': "cty:mBE",
            'last_deed_date': last_deed_date,
        }

        xml_id_mapping = report.section_report_ids.get_external_id()
        chosen_report_xml_ids = set(xml_id_mapping.values())
        chosen_pair = [pair for pair in REPORT_MATCHINGS if chosen_report_xml_ids.issuperset(pair[0])]
        if len(chosen_pair) != 1:
            raise UserError(_("Please add a single balance sheet and a single profit and loss report that have a matching (Abbr or Full) format for the XBRL export."))

        report_xmlids, template_xmlid = chosen_pair[0]
        balance_sheet_report = self.env.ref(report_xmlids[0])
        chosen_reports = report.section_report_ids.filtered(
            lambda r: xml_id_mapping.get(r.id) in report_xmlids
        )
        for chosen_report in chosen_reports:
            report_options = chosen_report.get_options({
                'date': {
                    'date_from': current_fiscal_date['date_from'],
                    'date_to': current_fiscal_date['date_to'],
                },
            })

            lines = chosen_report._get_lines(report_options)
            report_line_codes = {
                report_line.id: report_line.code
                for report_line in chosen_report.line_ids
            }
            balance_index = next((i for i, col in enumerate(report_options['columns']) if col['expression_label'] == 'balance'), -1)
            if balance_index == -1:
                raise UserError(_("The report used for XBRL export should have a 'balance' column."))
            for line in lines:
                balance_col = line.columns[balance_index]
                line_code = report_line_codes.get(balance_col.report_line_id)
                if line_code == 'BE_BS_499':
                    if balance_col.no_format > 0:
                        raise UserError(_("The 499 accounts should always be zero before exporting XBRL. Please correct your accounts and try again."))
                elif line_code:
                    data[line_code] = round(balance_col.no_format, 2)

        data.update(self._get_previous_balance_sheet_data(balance_sheet_report, options))
        data.update(self._get_disclosure_data(report, options))
        data.update(self._get_extra_file_data(options))

        report_template = self.env.ref(template_xmlid, raise_if_not_found=False)
        xbrl = self.env['ir.qweb']._render(report_template.id, data)
        xbrl_element = etree.fromstring(xbrl)
        xbrl_file = etree.tostring(xbrl_element, xml_declaration=True, encoding='utf-8')
        return {
            'file_name': report.get_default_report_filename(options, 'xbrl'),
            'file_content': xbrl_file,
            'file_type': 'xml',
        }

    def _get_previous_balance_sheet_data(self, report, options):
        """ Gets the balance sheet data of the previous fiscal year. The key is the same as the current period with a 'P' suffix. """
        previous_fiscal_date = self.env.company.compute_fiscalyear_dates(
            options['xbrl_current_fiscal_date']['date_from'] - relativedelta(days=1)
        )

        report_options = report.get_options({
            'date': {
                'date_from': previous_fiscal_date['date_from'],
                'date_to': previous_fiscal_date['date_to'],
            }
        })

        previous_period_data = {}
        lines = report._get_lines(report_options)
        report_line_codes = {
            report_line.id: report_line.code
            for report_line in report.line_ids
        }
        balance_index = next((i for i, col in enumerate(report_options['columns']) if col['expression_label'] == 'balance'), -1)
        for line in lines:
            balance_col = line.columns[balance_index]
            line_code = report_line_codes.get(balance_col.report_line_id)
            if line_code and line_code != 'BE_BS_499':
                previous_period_data[f'{line_code}P'] = round(balance_col.no_format, 2)
        return previous_period_data

    def _get_disclosure_data(self, report, options):

        def get_balance(custom_domain, date_scope='from_beginning'):
            domain = report._get_options_domain(options, date_scope) & Domain.AND([
                Domain('parent_state', '=', 'posted'),
                Domain(custom_domain),
            ])
            [(balance,)] = self.env['account.move.line']._read_group(domain, aggregates=['balance:sum'])
            balance = abs(balance) or 0.0
            return round(balance, 2)

        def get_account_code_domain(code_suffixes):
            return Domain.OR([Domain('account_id.code', '=like', account_code) for account_code in code_suffixes])

        date_to = fields.Date.to_date(options['date']['date_to'])
        one_year_mark = fields.Date.to_string(date_to + relativedelta(years=1))
        five_year_mark = fields.Date.to_string(date_to + relativedelta(years=5))

        extra_data_specs = [
        # Financial fixed assets
            # Acquisition value at the end of the period
            ('BE_EXP_8395', [('account_id.code', 'in', [
                '280000', '281000', '281100', '281200', '281700',
                '282000', '283000', '283100', '283200', '283700',
                '284000', '285000', '285100', '285200', '285700', '288000',
            ])]),
            # Capital gains at the end of the period
            ('BE_EXP_8455', [('account_id.code', '=like', '28_800')]),
            # Amounts written down at the end of the period
            ('BE_EXP_8525', [('account_id.code', '=like', '28_900')]),
            # Uncalled amounts at the end of the period
            ('BE_EXP_8555', [('account_id.code', 'in', ['280100', '282100', '284100'])]),
        # Tangible fixed assets
            # Acquisition value at the end of the period
            ('BE_EXP_8199', get_account_code_domain(['22%0', '23%0', '24%0', '25%0', '26%0', '27%0'])),
            # Revaluation surpluses at the end of the period
            ('BE_EXP_8259', get_account_code_domain(['22%8', '23%8', '24%8', '25%8', '26%8', '27%8'])),
            # Depreciations and amounts written down at the end of the period
            ('BE_EXP_8329', get_account_code_domain(['22%9', '23%9', '24%9', '25%9', '26%9', '27%9'])),
        # Amounts payable for more than 1 year
            # Amounts payable with a remaining term of more than one but not more than five years
            ('BE_EXP_8912', [
                ('account_id.code', '=like', '17%'),
                ('date_maturity', '>', one_year_mark),
                ('date_maturity', '<=', five_year_mark),
            ]),
            # Amounts payable with a remaining term of more than five years
            ('BE_EXP_8913', [
                ('account_id.code', '=like', '17%'),
                ('date_maturity', '>', five_year_mark),
            ]),
        # Depreciation written off formation expenses, intangible and tangible fixed assets
            # Formation expenses
            ('BE_EXP_8079', [('account_id.code', '=', '630000')], 'from_fiscalyear'),
            # Intangible and tangible fixed assets
            ('BE_EXP_8279', [('account_id.code', 'in', ['630100', '630800', '630200', '630900'])], 'from_fiscalyear'),
        ]

        disclosure_data = {}
        for code, domain, *args in extra_data_specs:
            disclosure_data[code] = get_balance(domain, *args)
        return disclosure_data

    def _get_extra_file_data(self, options):
        """Method to be overridden if some extra data should be passed to the file generator."""
        return {}

    def _validate_company_data(self):
        """Validates that the company has all required data for generating the XBRL file."""

        required_address_fields = ('vat', 'street', 'zip', 'l10n_be_region_id', 'l10n_be_company_type_id')
        missing_fields = []
        for field in required_address_fields:
            if not self.env.company[field]:
                missing_fields.append(self.env['res.company']._fields[field].string)

        if missing_fields:
            field = ', '.join(missing_fields)
            action = {
                'view_mode': 'form',
                'res_model': 'res.company',
                'type': 'ir.actions.act_window',
                'res_id': self.env.company.id,
                'views': [[self.env.ref('base.view_company_form').id, 'form']],
            }
            raise RedirectWarning(
                _("Please fill in the following company data before generating the XBRL file: %s", field),
                action,
                _("Go to company configuration")
            )
