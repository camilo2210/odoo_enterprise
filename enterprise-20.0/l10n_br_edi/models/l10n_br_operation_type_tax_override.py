from odoo import models, fields


class L10nBrOperationTypeTaxOverride(models.Model):
    _name = 'l10n_br.operation.type.tax.override'
    _description = "Operation Type Tax Override"

    l10n_br_operation_type_id = fields.Many2one(
        comodel_name='l10n_br.operation.type',
        required=True,
        ondelete='cascade',
    )
    tax_id = fields.Many2one(
        comodel_name='account.tax',
        required=True,
        string="Tax",
        domain=[('l10n_br_avatax_code', '!=', False)],
        ondelete='cascade',
        help="The tax for which CST and benefit code should be overwritten.",
    )
    l10n_br_avatax_code = fields.Char(
        related='tax_id.l10n_br_avatax_code',
        readonly=True,
    )
    cst_code = fields.Char(
        string="CST Code",
        help="Overrides the CST calculated by Avalara for the selected tax.",
    )
    benefit_code = fields.Char(
        string="Benefit Code",
        help="Overrides the fiscal benefit code calculated by Avalara for the selected tax.",
    )
    c_class_trib = fields.Char(
        string="Tax Classification Code",
        help="Brazil: IBS/CBS Taxation classification used to override the default value sent for tax calculation and invoicing.",
    )
