from odoo import api, fields, models


class ImportToSpreadsheet(models.TransientModel):
    _name = 'documents.import.to.spreadsheet'
    _description = 'Convert XLSX and CSV files to Odoo Spreadsheet'

    document_id = fields.Many2one('documents.document')
    archive_document = fields.Boolean(string="Move source file to trash", default=True)
    is_csv = fields.Boolean(compute='_compute_is_csv')
    csv_separator_type = fields.Selection(
        [
            ('auto_detect', 'Detect automatically'),
            ('comma', 'Comma'),
            ('semicolon', 'Semicolon'),
            ('tab', 'Tab'),
            ('custom', 'Custom'),
        ],
        string="Separator",
        default='auto_detect'
    )
    csv_separator = fields.Char(
        string="Custom separator",
        size=1,
        compute='_compute_csv_separator',
        readonly=False,
        store=True,
    )

    @api.depends('document_id')
    def _compute_is_csv(self):
        for record in self:
            record.is_csv = record.document_id.mimetype == 'text/csv'

    @api.depends('csv_separator_type')
    def _compute_csv_separator(self):
        for record in self:
            match record.csv_separator_type:
                case 'comma':
                    record.csv_separator = ','
                case 'semicolon':
                    record.csv_separator = ';'
                case 'tab':
                    record.csv_separator = '\t'
                case _:
                    record.csv_separator = False

    def import_to_spreadsheet(self):
        spreadsheet_document = self.document_id._import_to_spreadsheet(csv_separator=self.csv_separator)

        if self.archive_document:
            self.document_id.action_archive()
        return spreadsheet_document.action_open_spreadsheet()
