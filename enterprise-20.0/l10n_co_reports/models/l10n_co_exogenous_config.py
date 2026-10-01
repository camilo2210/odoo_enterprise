# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.addons.l10n_co_reports.models.l10n_co_exogenous_category import EXOGENOUS_REPORT_TYPES
from odoo.exceptions import ValidationError


class L10n_CoExogenousConfig(models.Model):
    _name = 'l10n_co.exogenous.config'
    _description = 'Colombian Exogenous Report Mapping'

    report_type = fields.Selection(
        string="Report",
        required=True,
        selection=EXOGENOUS_REPORT_TYPES,
    )
    value_to_report = fields.Selection(
        string="Value to Report",
        required=True,
        selection=[
            ('debit', 'Debit'),
            ('credit', 'Credit'),
            ('balance', 'Balance'),
        ],
    )
    concept = fields.Char(string="Concept")
    exogenous_category_id = fields.Many2one(
        string="Category",
        required=True,
        comodel_name='l10n_co.exogenous.category'
    )
    account_ids = fields.Many2many(
        comodel_name="account.account",
        relation="account_account_exogenous_config",
    )

    # === Misc Information === #
    category_sequence = fields.Integer(
        related="exogenous_category_id.sequence",
    )
    show_concept = fields.Boolean(
        compute="_compute_show_concept",
    )
    allowed_account_ids = fields.Many2many(
        comodel_name="account.account",
        compute="_compute_allowed_account_ids",
    )

    @api.constrains('concept')
    def _check_concept(self):
        for config in self:
            if config.show_concept and not config.concept:
                raise ValidationError(_('The concept for report type, "%s", must be specified.', config.report_type))

    @api.constrains('exogenous_category_id')
    def _check_category(self):
        for config in self:
            report_type = config.report_type
            category = config.exogenous_category_id
            if category.report_type != report_type:
                raise ValidationError(_(
                    'The exogenous category, "%(category_name)s", is not applicable to report %(report_type)s.',
                    category_name=category.name,
                    report_type=report_type))

    @api.constrains('account_ids')
    def _check_accounts(self):
        for config in self:
            if bad_accounts := config.account_ids - config.allowed_account_ids:
                raise ValidationError(_(
                    "The following accounts are not allowed for the report type - %s.\n"
                    "Please review the following:\n"
                    "- Report 1008 uses asset accounts.\n"
                    "- Report 1009 uses liability accounts.",
                    bad_accounts.mapped('code')))

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('report_type', 'value_to_report', 'exogenous_category_id')
    def _compute_display_name(self):
        for config in self:
            if config._origin:
                config.display_name = f"[{config.report_type}] {config.value_to_report} {config.exogenous_category_id.name}"
            else:
                config.display_name = ""

    @api.depends('report_type')
    def _compute_show_concept(self):
        for config in self:
            config.show_concept = config.report_type not in ['1005', '1006']

    @api.depends('report_type')
    def _compute_allowed_account_ids(self):
        report_type_to_account_type = {
            '1008': 'asset',
            '1009': 'liability',
        }
        for config in self:
            account_type = report_type_to_account_type.get(config.report_type)
            if account_type:
                config.allowed_account_ids = self.env['account.account'].search([('account_type', '=like', f"{account_type}_%")])
            else:
                config.allowed_account_ids = self.env['account.account'].search([])
