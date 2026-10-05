import base64
from lxml import etree
from datetime import date

from odoo import models, fields, _
from odoo.tools import float_round
from odoo.tools.business_data import street_split
from odoo.exceptions import RedirectWarning


class SlovakianAnnualStatementsCustomHandler(models.AbstractModel):
    """
        Generate the Balance Sheet and P&L report for Slovakia.
        Generated using as a reference the documentation at
        https://www.financnasprava.sk/sk/danovi-a-colni-specialisti/technicke-informacie/podklady-pre-tvorcov-sw/eform-specifikacia
    """
    _name = 'l10n_sk.annual.statements.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Slovakian Annual Statements Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options.setdefault('buttons', []).append({
            'name': _('XML'),
            'sequence': 30,
            'action': 'open_report_export_wizard',
        })

    def _build_xml(self, options, type_of_closing, accounting_unit_size):
        report = self.env['account.report'].browse(options['sections_source_id'])
        values = {}
        values['company'] = report._get_sender_company_for_export(options)
        values = self._check_and_insert_company_info(values)
        values = self._insert_dates_info(values, report, options)
        # Input the wizard params so that the chosen values are set to 1 while the others remain 0
        values.update(dict.fromkeys(['regular', 'extraordinary', 'interim', 'small', 'large'], "0"))
        values[type_of_closing] = "1"
        if accounting_unit_size:
            values[accounting_unit_size] = "1"
        xml_content = self.env['ir.qweb']._render('l10n_sk_reports.sk_annual_statements_template', values=values)
        tree = etree.fromstring(xml_content)

        def get_section_lines(section_id, options):
            report_section = self.env['account.report'].browse(section_id)
            section_options = report_section.get_options(previous_options={
                **options,
                'selected_section_id': section_id,
                'comparison': {
                    'filter': 'previous_period',
                    'number_period': 1,
                },
                'export_mode': 'file',
            })
            return report_section._get_lines(section_options)

        balance_sheet_lines = get_section_lines(options['sections'][0]['id'], options)
        profit_loss_lines = get_section_lines(options['sections'][1]['id'], options)

        report_sections = [
            {
                'node': '//ucPod1Suvaha',  # Súvaha:AKTÍVA section
                'lines': balance_sheet_lines[:78],
                'starting_num_r': 1,
                'starting_num_s': 1,
                'num_width': 3,
            }, {
                'node': '//ucPod1Suvaha',  # Súvaha:PASÍVA section
                'lines': balance_sheet_lines[78:],
                'starting_num_r': 79,
                'starting_num_s': 5,
                'num_width': 3,
            }, {
                'node': '//ucPod2VykazZS',
                'lines': profit_loss_lines,
                'starting_num_r': 1,
                'starting_num_s': 1,
                'num_width': 2,
            },
        ]

        for index, section in enumerate(report_sections):
            section_node = tree.xpath(section['node'])[0]
            for index2, line in enumerate(section['lines']):
                elem = etree.SubElement(section_node, "r" + str(index2 + section['starting_num_r']).zfill(section['num_width']))
                if index == 0:  # For the Súvaha:AKTÍVA section of the report we only need the last column (net) from the previous period
                    columns = line.columns[:3] + [line.columns[5]]
                elif index == 1:  # For the Súvaha:PASÍVA section of the report we only need the last column (net) from both periods
                    columns = [line.columns[2]] + [line.columns[5]]
                else:
                    columns = line.columns
                for index3, col in enumerate(columns):
                    sub_elem = etree.SubElement(elem, "s" + str(index3 + section['starting_num_s']))
                    value = col.no_format or 0
                    sub_elem.text = str(float_round(value, precision_digits=0))

        formatted_xml = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')
        return base64.b64encode(formatted_xml)

    def _check_and_insert_company_info(self, values):
        company = values['company']
        company_values_needed = [company.income_tax_id, company.partner_id._get_additional_identifier('SK_EN'), company.l10n_sk_nace_code, company.zip, company.city]
        company_values_names = [_('Income Tax ID'), _('Company ID'), _('SK NACE Code'), _('ZIP'), _('City')]
        if not all(company_values_needed):
            missing_values = ", ".join([company_values_names[i] for i, val in enumerate(company_values_needed) if not val])
            raise RedirectWarning(
                message=_("Please make sure that the following are set for your company: %s.", missing_values),
                action=company._get_records_action(name=_("Company: %s", company.name), target='new'),
                button_text=_("Go to Company"),
            )

        values['SK_NACE_code1'] = company.l10n_sk_nace_code[:2]
        values['SK_NACE_code2'] = company.l10n_sk_nace_code[2:4]
        values['SK_NACE_code3'] = company.l10n_sk_nace_code[4]
        street_split_values = street_split(company.partner_id.street)
        values['street_name'] = street_split_values['street_name']
        values['street_number'] = street_split_values['street_number']

        return values

    def _insert_dates_info(self, values, report, options):
        values['creation_date'] = date.today().strftime("%Y-%m-%d")
        values['from_date'] = fields.Date.to_date(options['date']['date_from'])
        values['to_date'] = fields.Date.to_date(options['date']['date_to'])

        previous_period = report._get_shifted_dates_period(options, options['date'], -1)
        values['previous_from_date'] = fields.Date.to_date(previous_period['date_from'])
        values['previous_to_date'] = fields.Date.to_date(previous_period['date_to'])

        return values

    def open_report_export_wizard(self, options):
        """ Creates a new export wizard for this report."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Annual Statements XML Export'),
            'view_mode': 'form',
            'res_model': 'l10n_sk.generate.annual.statements.report',
            'target': 'new',
            'views': [(self.env.ref('l10n_sk_reports.view_l10n_sk_generate_annual_statements_report').id, 'form')],
            'context': {'default_options': options},
        }
