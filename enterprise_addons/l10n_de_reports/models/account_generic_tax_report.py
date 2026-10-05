from odoo import api, models, _
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import float_compare, float_is_zero, float_repr

from lxml import etree
from datetime import date, datetime

TAX_BASE_CODES = {'21', '35', '41', '42', '43', '44', '45', '46', '48', '49', '50', '60', '73',
                  '76', '77', '81', '84', '86', '87', '89', '91', '93', '90', '94', '95'}

BASE_CODE_TO_TAX_CODE = {'35': '36', '76': '80', '95': '98', '94': '96', '46': '47', '73': '74', '84': '85'}


class L10n_DeTaxReportHandler(models.AbstractModel):
    _name = 'l10n_de.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'German Tax Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.setdefault('buttons', []).append(
            {
                'name': _('XML'),
                'sequence': 30,
                'action': 'export_file',
                'action_param': 'export_tax_report_to_xml',
                'file_export_type': _('XML'),
            }
        )

    @api.model
    def _redirect_to_misconfigured_company_number(self, message):
        """ Raises a RedirectWarning informing the user his company is missing configuration, redirecting him to the
         list view of res.company
        """
        action = self.env.ref('base.action_res_company_form')

        raise RedirectWarning(
            message,
            action.id,
            _("Configure your company"),
        )

    def export_tax_report_to_xml(self, options):

        def insert_line(code, value):

            # 83 must be there regardless of it's value
            if code == '83':
                elem = etree.SubElement(taxes, 'Kz83')
                elem.text = float_repr(value, 2)
                return

            # Some lines were made for intermediate calculations or guidance only and shouldn't be reported (ex DE_LINE36)
            if not (value and code.isnumeric()):
                return

            formatted_value = (
                float_repr(int(value), 0)
                if code in TAX_BASE_CODES
                else float_repr(value, 2)
            )

            # all "Kz" may be supplied as negative, except "Kz37", "Kz39", "Kz50"
            value = float(formatted_value)
            if float_is_zero(value, 2) or code in ('37', '39', '50') and float_compare(value, 0.0, 2) == -1:
                return

            elem = etree.SubElement(taxes, f'Kz{code}')
            elem.text = formatted_value

        if self.env.company.l10n_de_stnr:
            steuer_nummer = self.env.company.get_l10n_de_stnr_national()
        else:
            self._redirect_to_misconfigured_company_number(_("Your company's SteuerNummer field should be filled"))

        report = self.env['account.report'].browse(options['report_id'])
        template_context = {}
        options = report.get_options(options)
        date_to = datetime.strptime(options['date']['date_to'], '%Y-%m-%d')
        template_context['year'] = date_to.year
        periodicity = options['return_periodicity']['periodicity']
        if periodicity == 'monthly':
            template_context['period'] = date_to.strftime("%m")
        elif periodicity == 'trimester':
            month_end = date_to.month
            if month_end % 3 != 0:
                raise UserError(self.env._("Quarter not supported."))
            # For quarters, the period should be 41, 42, 43, 44 depending on the quarter.
            template_context['period'] = month_end // 3 + 40
        template_context['creation_date'] = date.today().strftime("%Y%m%d")
        template_context['company'] = report._get_sender_company_for_export(options)

        qweb = self.env['ir.qweb']
        doc = qweb._render('l10n_de_reports.tax_export_xml', values=template_context)
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(doc, parser)

        taxes = tree.xpath('//*[local-name()="Umsatzsteuervoranmeldung"]')[0]
        tax_number = taxes.xpath('*[local-name()="Steuernummer"]')[0]
        tax_number.text = steuer_nummer

        # Add the values dynamically. We do it here because the tag is generated from the code and
        # Qweb doesn't allow dynamically generated tags.

        report_lines = report._get_lines(options)
        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        report_line_ids = [line.columns[0].report_line_id for line in report_lines]
        codes_context = {}
        for record in self.env['account.report.line'].browse(report_line_ids):
            codes_context[record.id] = record.code

        to_insert = []

        for line in report_lines:
            line_code = codes_context[line.columns[0].report_line_id]
            if not (line_code and line_code.startswith('DE') and not line_code.endswith('TAX')):
                continue
            line_code = line_code.split('_')[1]
            if 'balance' in colname_to_idx:
                line_value = line.columns[colname_to_idx['balance']].no_format
            else:
                tax_value = line.columns[colname_to_idx['tax']].no_format
                base_value = line.columns[colname_to_idx['base']].no_format

                if tax_code := BASE_CODE_TO_TAX_CODE.get(line_code):
                    to_insert.append((tax_code, tax_value))

                line_value = base_value or tax_value
            to_insert.append((line_code, line_value))

        for code, value in sorted(to_insert):
            insert_line(code, value)

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': etree.tostring(tree, pretty_print=True, standalone=False, encoding='ISO-8859-1',),
            'file_type': 'xml',
        }
