from odoo import api, models


class L10NHUAccountIntrastatGoodsReportHandler(models.AbstractModel):
    _inherit = 'account.intrastat.goods.report.handler'

    def hu_intrastat_export_to_csv(self, options):
        options['export_mode'] = 'file'
        goods_submission_wizard = self.env['l10n_hu_intrastat.intrastat.goods.submission.wizard'].browse(options['l10n_hu_intrastat_goods_submission_wizard_id'])
        contact_executive = goods_submission_wizard.l10n_hu_intrastat_contact_executive
        contact_executive_status = goods_submission_wizard.l10n_hu_intrastat_contact_executive_status
        contact_person = goods_submission_wizard.l10n_hu_intrastat_contact_person
        report = self.env['account.report'].browse(options['report_id'])
        results = self._hu_intrastat_get_report_results_for_file_export(options, report)
        file_content = self._hu_intrastat_get_csv_file_content(results, options, contact_executive, contact_executive_status, contact_person)
        return {
            'file_name': report.get_default_report_filename(options, 'csv'),
            'file_content': file_content,
            'file_type': 'csv',
        }

    @api.model
    def _hu_intrastat_get_report_results_for_file_export(self, options, report):
        expressions = report.line_ids.expression_ids
        return self._report_engine_intrastat(options, expressions[0].date_scope, expressions.grouped('formula'), 'id', None)[expressions]

    def _hu_intrastat_get_csv_file_content(self, results, options, contact_executive, contact_executive_status, contact_person):
        file_content = self._hu_intrastat_get_csv_file_content_header(options.get('date', {}), contact_executive, contact_executive_status, contact_person)
        origin_country_code = self.env.company.country_code

        for idx, (_trash, result) in enumerate(results, start=1):
            file_content += ';'.join([
                str(idx),
                result.get('commodity_code') or '',
                result.get('transaction_code') or '',
                result.get('country_code') or '',
                origin_country_code,
                result.get('weight') or '',
                result.get('supplementary_units') or '',
                str(result.get('value')) or '',
                str(result.get('value')) or '',
                result.get('partner_vat') or '',
                ';;;;\n',
            ])

        return file_content

    def _hu_intrastat_get_csv_file_content_header(self, date_options, contact_executive, contact_executive_status, contact_person):
        reporting_year = date_options.get('date_to').split('-')[0][-2:]
        reporting_month = date_options.get('date_to').split('-')[1]
        company = self.env.company
        values_mapping = {
            'MC01': '2010',
            'M003_G': company.vat or '',  # tax ID number of organization
            'M003': company.vat or '',  # Specialized unit, or tax ID nr
            'MEV': reporting_year,
            'MHO': reporting_month,
            'JHNEV': contact_executive.name or '',  # name of the executive contact
            'JBEOSZTAS': contact_executive_status,  # status of the executive contact
            'JTELEFON': contact_executive.phone or '',  # phone of the executive contact
            'JEMAIL': contact_executive.email or '',  # email of the executive contact
            'KNEV': contact_person.name or '',  # name of the contact person
            'KTELEFON': contact_person.phone or '',  # phone of the contact person
            'KEMAIL': contact_person.email or '',  # email of the contact person
            'MEGJEGYZES': '',  # comment max 500 chars
            'VGEA002': '',  # time spent filling the questionnaire (minutes)
        }
        white_line = ';;;;;;;;;;;;;;'
        file_header = '\n'.join([
            '{fejezet;sorrend};;;;;;;;;;;;;',
            '0;1;;;;;;;;;;;;;',
            white_line,
            f"{{{';'.join(values_mapping.keys())}}}",
            f"{';'.join(values_mapping.values())}",
            white_line,
            '{fejezet;sorrend};;;;;;;;;;;;;',
            '1;1;;;;;;;;;;;;;',
            white_line,
            '{T_SORSZ;TEKOD;UKOD;RTA;SZAORSZ;KGM;KIEGME;SZAOSSZ;STAERT;PADO};;;;;',
            '',
        ])

        return file_header
