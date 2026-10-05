from odoo import api, fields, models


class L10nDoEdiDocumentTypeRange(models.Model):
    _name = 'l10n_do_edi.document.type.range'
    _description = 'Dominican Republic EDI Authorized Document Type Range'

    start_number = fields.Integer('Starting Sequence Number')
    end_number = fields.Integer('Ending Sequence Number')
    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    expiration_date = fields.Date('Expiration Date')

    _check_positive_numbers = models.Constraint(
        'CHECK(start_number > 0 AND end_number > 0 AND start_number <= end_number)',
        'Starting and ending sequence numbers must be positive non-zero values, and the starting number must come before the ending number.',
    )

    @api.depends('company_id', 'start_number', 'end_number')
    def _compute_display_name(self):
        for record in self:
            if record.start_number:
                record.display_name = f"Document Range {record.start_number}-{record.end_number}"
            else:
                record.display_name = ""
