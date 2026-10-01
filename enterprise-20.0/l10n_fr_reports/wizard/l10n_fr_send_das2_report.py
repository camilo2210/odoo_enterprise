from lxml import etree

from odoo import Command, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes, cleanup_xml_node


class L10nFrSendDAS2Report(models.TransientModel):
    _name = 'l10n_fr.send.das2.report'
    _description = "Send DAS2 Report Wizard"

    year = fields.Char(string="Year", readonly=True, required=True)
    contact_person = fields.Many2one(
        comodel_name='res.partner',
        string="Point of Contact",
        help="The person to contact regarding the DAS2 report",
        default=lambda self: self.env.user.partner_id.id,
    )
    return_id = fields.Many2one(
        comodel_name='account.return',
    )

    def _export_das2_report(self):
        report = self.env.ref('l10n_fr_reports.account_report_l10n_fr_das2_report')
        vals = self.env['l10n_fr.das2.report.handler']._prepare_edi_values(
            report.get_options({
                'date': {
                    'date_from': f'{self.year}-01-01',
                    'date_to': f'{self.year}-12-31',
                },
            }),
            self.contact_person,
            self.year,
            self.env['account.report.async.document']._is_aspone_test_mode(),
        )

        xml = self.env['ir.qweb']._render("l10n_fr_reports.das2_aspone_xml_edi", vals)
        try:
            xml.encode('ISO-8859-15')
        except UnicodeEncodeError as e:
            raise UserError(
                self.env._("The xml file generated contains an invalid character: '%s'", xml[e.start:e.end]))

        xml = etree.tostring(cleanup_xml_node(xml), encoding='ISO-8859-15', standalone='yes')

        return {
            'file_name': f"DAS2_{self.env.company.name}_{self.year}.xml",
            'file_content': xml,
        }

    def action_send_das2_report(self):
        das2_xml = self._export_das2_report()
        xml_content = das2_xml['file_content']
        export_name = das2_xml['file_name']

        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        endpoint = self.env['account.report.async.document']._get_aspone_endpoint()
        response = self.env['account.report.async.document']._get_fr_webservice_answer(
            url=f"{endpoint}/api/l10n_fr_aspone/2/add_document",
            params={
                'db_uuid': db_uuid,
                'xml_content': xml_content.decode('iso8859_15'),
                'procedure': 'PART',
            },
        )

        deposit_uid = ''
        if response['success']:
            deposit_uid = response['data']['deposit_id']

            if self.return_id:
                # If there are no errors when sending, we put the return state as submitted
                self.return_id.write({
                    'state': 'submitted',
                    'is_completed': True,
                })

        if not deposit_uid:
            raise UserError(self.env._("Error occurred while sending the report to the government : '%(response)s'", response=str(response)))

        document = self.env['account.report.async.document'].create({
            'name': export_name,
            'attachment_name': export_name,
            'attachment': BinaryBytes(xml_content),
            'deposit_uid': deposit_uid,
            'state': 'sent',
        })

        self.env['account.report.async.export'].create({
            'name': self.env._("DAS2 Report %s", self.year),
            'document_ids': [Command.set([document.id])],
            'date_from': fields.Date.from_string(f'{self.year}-01-01'),
            'date_to': fields.Date.from_string(f'{self.year}-12-31'),
            'report_id': self.env.ref('l10n_fr_reports.account_report_l10n_fr_das2_report').id,
            'recipient': 'DGI_EDI_PART',
        })
