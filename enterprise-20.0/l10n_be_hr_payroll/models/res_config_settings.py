# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    onss_expeditor_number = fields.Char(
        related="company_id.onss_expeditor_number",
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    onss_certificate_id = fields.Many2one(
        related="company_id.onss_certificate_id",
        readonly=False)
    onss_technical_user_name = fields.Char(
        related="company_id.onss_technical_user_name",
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    onss_sftp_private_key = fields.Many2one(
        related="company_id.onss_sftp_private_key",
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    nsso_immatriculation_date = fields.Date(
        related="company_id.nsso_immatriculation_date",
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_environment = fields.Selection(
        related='company_id.l10n_be_dimona_environment',
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user')
    module_pos_blackbox_be = fields.Boolean(string="POS Blackbox BE")
    l10n_be_cash_register_active = fields.Boolean(
        related='company_id.l10n_be_cash_register_active',
        readonly=False)
    l10n_be_cash_register_number = fields.Char(
        related='company_id.l10n_be_cash_register_number',
        readonly=False)
    l10n_be_cash_register_registration_start = fields.Date(
        related='company_id.l10n_be_cash_register_registration_start',
        readonly=False)
    l10n_be_cash_register_registration_end = fields.Date(
        related='company_id.l10n_be_cash_register_registration_end',
        readonly=False)
    l10n_be_daily_registration_recording = fields.Selection(
        related='company_id.l10n_be_daily_registration_recording',
        readonly=False)
    l10n_be_employer_category_has_cp302 = fields.Boolean(
        related='company_id.l10n_be_employer_category_has_cp302')
    l10n_be_max_unused_cars = fields.Integer(string='Maximum unused cars', default=5,
        related="company_id.l10n_be_max_unused_cars", readonly=False, store=True
    )
    l10n_be_temporary_car_option = fields.Boolean(related="company_id.l10n_be_temporary_car_option",
        readonly=False, store=True)
    l10n_be_cbe_inscription = fields.Date(
        related='company_id.l10n_be_cbe_inscription',
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_be_has_white_cash_register = fields.Boolean(
        related='company_id.l10n_be_has_white_cash_register',
        readonly=False
    )

    def action_open_hr_payroll_localization(self):
        return {
            'name': self.env._('Payroll Localization'),
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.config.settings',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.company_id.id)],
            'target': 'current',
        }
