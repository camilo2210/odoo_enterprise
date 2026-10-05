import re
from markupsafe import Markup
from stdnum.ro.cui import compact

from odoo import models
from odoo.exceptions import UserError
from odoo.fields import Date
from odoo.tools import float_round


def _raw_phonenumber(phonenumber):
    return re.sub(r"[^+0-9]", "", phonenumber)[:20]


class L10n_RoEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_ro.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Romanian EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        """
        Add the invoice lines search domain that is specific to the country.
        Typically, the taxes account.report.expression ids relative to the country for the triangular, sale of goods
        or services.
        :param dict options: Report options
        :return dict: The modified options dictionary
        """
        ro_tax_tags = self._get_ec_sales_tax_tags()
        op_type_map = {
            'goods': (self.env._('Goods'), 'L'),
            'services': (self.env._('Services'), 'P'),
            'triangular': (self.env._('Triangular'), 'T'),
            'goods_acquisition': (self.env._('Goods Acquisition'), 'A'),
            'services_acquisition': (self.env._('Services Acquisition'), 'S'),
        }
        options.update({
            'sales_report_operation_types': {
                op_type: {
                    'tax_tag_ids': ro_tax_tags.get(op_type, []),
                    'name': label,
                    'shortcut': shortcut,
                }
                for op_type, (label, shortcut) in op_type_map.items()
            },
        })

        super()._custom_options_initializer(report, options, previous_options)

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        expressions_xmlid = {
            'goods': ('l10n_ro_reports_d390.account_tax_report_ro_baza_rd1_tax_tag',),
            'services': ('l10n_ro.account_tax_report_ro_baza_rd3_tag',),
            'triangular': ('l10n_ro_reports_d390.account_tax_report_ro_baza_rd1T_tax_tag',),
            'goods_acquisition': (
                'l10n_ro.account_tax_report_ro_baza_rd5_tag',
                'l10n_ro.account_tax_report_ro_baza_rd20_tag',
            ),
            'services_acquisition': (
                'l10n_ro.account_tax_report_ro_baza_rd7_tag',
                'l10n_ro.account_tax_report_ro_baza_rd22_tag',
            ),
        }

        ec_sales_tax_tags = {}
        for op_type, xmlids in expressions_xmlid.items():
            expressions = self.env['account.report.expression']
            for xmlid in xmlids:
                expressions |= self.env.ref(xmlid)
            ec_sales_tax_tags[op_type] = expressions._get_matching_tags().ids
        return ec_sales_tax_tags

    def export_to_xml_sales_report(self, options):
        # Check & Prepare data
        data_operation_info = data_partner_info = ''
        report = self.env['account.report'].browse(options['report_id'])
        return_id = self.env['account.return'].browse(options.get('return_id'))
        sender_company = report._get_sender_company_for_export(options)

        company_vat = report.get_vat_for_export(options)
        if not company_vat:
            raise UserError(self.env._("No VAT number associated with %s.", sender_company.name))
        phone = _raw_phonenumber(sender_company.phone)
        date_from = Date.to_date(options['date'].get('date_from'))

        # Get declaration information, collected from the 'Romanian EC Sales Report Generation Wizard'
        if not all([return_id.l10n_ro_declarant_surname, return_id.l10n_ro_declarant_name, return_id.l10n_ro_declarant_role]):
            raise UserError(self.env._("Following declaration information are missing for generating the D390 XML file:\n"
                "Name, Surname, Job Role."))

        necessary_details = {
            'first_name': return_id.l10n_ro_declarant_surname,
            'middle_name': return_id.l10n_ro_declarant_name,
            'job_position': return_id.l10n_ro_declarant_role,
            'fiscal_address': return_id.l10n_ro_fiscal_address or sender_company.partner_id.contact_address_inline,
            'fax': Markup("""
    fax="%(fax)s" """) % {'fax': return_id.l10n_ro_fax} if return_id.l10n_ro_fax else ''
        }

        operations = 0
        amount_type = {}
        partners_details = {}
        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        lines = report._get_lines(options)
        lines_except_totals = [
            line
            for line in lines
            if isinstance(report._get_markup(line.id), dict) and report._get_markup(line.id).get('groupby') == 'partner_id_and_sale_type'
        ]
        total_index = -1 if self.env.company.totals_below_sections else 0
        total_amount = int(float_round(lines[total_index].columns[colname_to_idx['balance']].no_format if lines else 0, precision_digits=0))

        for line in lines_except_totals:
            code = line.columns[colname_to_idx['sale_type_shortcut']].name[:1]
            country = line.columns[colname_to_idx['country_code']].name or ''
            vat = line.columns[colname_to_idx['vat_number']].name or ''
            amount = line.columns[colname_to_idx['balance']].no_format
            if not int(float_round(amount, precision_digits=0)):
                continue
            if not vat:
                raise UserError(self.env._('No vat number defined for %s.', line.name))
            operations += 1
            amount_type[code] = int(float_round((amount_type.get(code, 0) + amount), precision_digits=0))

            # partners mapping for <cos> section
            partners_details[vat] = country

            # <operatie> section
            data_operation_info += Markup("""
    <operatie tip="%(code)s" tara="%(country)s" codO="%(vatnum)s" denO="%(name)s" baza="%(amount)s"/>""") % {
                'code': code,
                'country': country,
                'vatnum': vat,
                'name': line.name,
                'amount': int(float_round(amount, precision_digits=0)),
            }

        # <cos> section
        for vat, country in partners_details.items():
            data_partner_info += Markup("""
    <cos tip="A" tara_m1="%(country)s" cod_m1="%(vatnum)s"/>""") % {'country': country, 'vatnum': vat}

        # header details for <declaratie390> and <rezumat> section
        xml_data = {
            **necessary_details,
            'company_name': sender_company.name,
            'vatnum': compact(company_vat),
            'email': Markup("""
    mail="%(email)s" """) % {'email': sender_company.email} if sender_company.email else '',
            'phone': Markup("""
    telefon="%(phone)s" """) % {'phone': phone} if phone else '',
            'year': date_from.year,
            'month': date_from.month,
            'rectification': int(bool(return_id.l10n_ro_d390_corrective_declaration)),
            'number_of_pages': (operations + 24) // 25,  # Each page can contain max 25 operations
            'total_operation': operations,
            'amount_sum': total_amount,
            'amount_checksum': (total_amount + operations),
            **{f'amount_{k}': amount_type.get(k, 0) for k in ('L', 'T', 'A', 'P', 'S', 'R')},
        }

        # header section <declaratie390> and <rezumat>
        data_head = Markup("""<declaratie390 xmlns="mfp:anaf:dgti:d390:declaratie:v3"
    luna="%(month)s"
    an="%(year)s"
    d_rec="%(rectification)s"
    nume_declar="%(middle_name)s"
    prenume_declar="%(first_name)s"
    functie_declar="%(job_position)s"
    cui="%(vatnum)s"
    den="%(company_name)s"
    adresa="%(fiscal_address)s"%(phone)s%(fax)s%(email)s
    totalPlata_A="%(amount_checksum)s">

    <rezumat
        nr_pag="%(number_of_pages)s"
        nrOPI="%(total_operation)s"
        bazaL="%(amount_L)s"
        bazaT="%(amount_T)s"
        bazaA="%(amount_A)s"
        bazaP="%(amount_P)s"
        bazaS="%(amount_S)s"
        bazaR="%(amount_R)s"
        total_baza="%(amount_sum)s"/>
        """) % xml_data

        data_rslt = data_head + data_partner_info + Markup("""
        """) + data_operation_info + Markup("""

</declaratie390>""")

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': data_rslt.encode('utf-8'),
            'file_type': 'xml',
        }
