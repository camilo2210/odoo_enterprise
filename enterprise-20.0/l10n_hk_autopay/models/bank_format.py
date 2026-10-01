# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class L10nhkBankFormat(models.AbstractModel):
    """
    Base model for Hong Kong bank file export.
    Provides the base functionality that provides the validation and generation methods for Hong Kong bank file export,
    as well as some helper tools shared by multiple bank formats.
    """
    _name = 'l10n_hk.bank.format'
    _description = "Hong Kong Bank File Export"

    running_total = fields.Float()
    transaction_count = fields.Integer()

    @api.model
    def _validate(self, file_format, payload):
        return []

    @api.model
    def _generate(self, file_format, payload):
        raise NotImplementedError()

    @api.model
    def _amount_in_cents(self, amount):
        return round(amount * 100)

    @api.model
    def _prepare_file_name(self, file_type, document_name):
        timestamp = fields.Datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{file_type}_{document_name}_{timestamp}"
