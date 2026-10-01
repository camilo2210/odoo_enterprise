from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes


class L10nFrReportsSendFiscalDeclaration(models.TransientModel):
    _name = 'l10n_fr_reports.send.fiscal.declaration'
    _description = "Send Fiscal Declaration Wizard"

    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    report_id = fields.Many2one(
        comodel_name='account.report',
        required=True,
    )
    return_id = fields.Many2one(
        comodel_name='account.return',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
    )
    tax_type = fields.Selection(
        string="Type of tax",
        selection=[
            ('IS', "Corporate tax (IS)"),
            ('IR', "Income tax (IR)"),
        ],
        default='IS',
        required=True,
    )
    special_circ = fields.Selection(
        string="Transfer/cessation of business or special circumstances",
        selection=[
            ('NOR', "Not applicable"),
            ('CSS', "Transfer or termination"),
            ('DCD', "Death"),
            ('DPR', "Provisional declaration"),
        ],
        default='NOR',
        required=True,
    )
    send_2033A = fields.Boolean(string="2033 A - Simplified Balance Sheet", default=True)
    send_2033B = fields.Boolean(string="2033 B - Simplified Profit and Loss", default=True)
    send_2033C = fields.Boolean(string="2033 C - Fixed Assets – Depreciation", default=True)
    send_2033D = fields.Boolean(string="2033 D - Statement of Provisions, Depreciation & Deficits", default=True)
    send_2033E = fields.Boolean(string="2033 E - Added value", default=True)
    send_2033F = fields.Boolean(string="2033 F - Share capital structure", default=True)
    send_2033G = fields.Boolean(string="2033 G - Subsidiaries and Investments", default=True)
    send_2031 = fields.Boolean(
        string="2031-SD - Income tax",
        readonly=True,
        compute='_compute_report_to_send',
    )
    send_2065 = fields.Boolean(
        string="2065-SD - Corporate tax return",
        readonly=True,
        compute='_compute_report_to_send',
    )
    send_2069 = fields.Boolean(string="2069 - Tax credits", default=True)

    @api.depends('tax_type')
    def _compute_report_to_send(self):
        for record in self:
            record.send_2031 = record.tax_type == 'IR'
            record.send_2065 = record.tax_type == 'IS'

    def action_send_fiscal_declaration(self):
        options = self.return_id._get_closing_report_options()
        options.update({
            'fiscal_declaration': {
                '2033A': self.send_2033A,
                '2033B': self.send_2033B,
                '2033C': self.send_2033C,
                '2033D': self.send_2033D,
                '2033E': self.send_2033E,
                '2033F': self.send_2033F,
                '2033G': self.send_2033G,
                '2031': self.send_2031,
                '2031BIS': self.send_2031,
                '2065': self.send_2065,
                '2065BIS': self.send_2065,
                '2069RCI': self.send_2069,
                'special_circ': self.special_circ,
                'tax_type': self.tax_type,
            }
        })
        xml_data = self.env['l10n_fr_reports.fiscal_declaration_handler']._export_fiscal_declaration(options)
        decoded_xml_content = xml_data['file_content'].decode('iso8859_15')
        export_name = xml_data['file_name']

        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        endpoint = self.env['account.report.async.document']._get_aspone_endpoint()
        response = self.env['account.report.async.document']._get_fr_webservice_answer(
            url=f"{endpoint}/api/l10n_fr_aspone/2/add_document",
            params={
                'db_uuid': db_uuid,
                'xml_content': decoded_xml_content,
                'procedure': 'TDFC',
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
            'attachment': BinaryBytes(decoded_xml_content.encode()),
            'deposit_uid': deposit_uid,
            'state': 'sent',
        })

        self.env['account.report.async.export'].create({
            'name': self.env._("Fiscal Declaration %s", self.date_to.year),
            'document_ids': [Command.set([document.id])],
            'date_from': fields.Date.from_string(self.date_from),
            'date_to': fields.Date.from_string(self.date_to),
            'report_id': self.env.ref('l10n_fr_reports.fiscal_declaration').id,
            'recipient': 'DGI_EDI_TDFC',
        })

        return {'type': 'ir.actions.act_window_close'}

    def open_sso_link(self):
        return self.env['l10n_fr_reports.aspone.sso.wizard']._action_redirect(self.env.company)
