# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_co_edi_header_actividad_economica = fields.Char(string='Economic Activity')
    l10n_co_edi_operation_mode_ids = fields.One2many(
        string="DIAN Operation Modes",
        comodel_name="l10n_co_edi.operation_mode",
        inverse_name="company_id",
    )
    l10n_co_edi_certificate_ids = fields.One2many(comodel_name='certificate.certificate', inverse_name='company_id')
    l10n_co_edi_test_environment = fields.Boolean(
        string="Test environment",
        inverse='_inverse_l10n_co_edi_test_environment',
        default=True,
    )
    l10n_co_edi_certification_process = fields.Boolean(
        compute='_compute_l10n_co_edi_certification_process',
        inverse='_inverse_l10n_co_edi_certification_process',
        store=True,
        readonly=False,
    )
    l10n_co_edi_demo_mode = fields.Boolean(
        compute='_compute_l10n_co_edi_demo_mode',
        inverse='_inverse_l10n_co_edi_demo_mode',
    )

    @api.depends('l10n_co_edi_test_environment')
    def _compute_l10n_co_edi_certification_process(self):
        for company in self:
            if not company.l10n_co_edi_test_environment:
                company.l10n_co_edi_certification_process = False

    def _inverse_l10n_co_edi_certification_process(self):
        for company in self:
            if company.l10n_co_edi_certification_process and not company.l10n_co_edi_test_environment:
                company.l10n_co_edi_certification_process = False

    def _compute_l10n_co_edi_demo_mode(self):
        for company in self:
            company.l10n_co_edi_demo_mode = self.env['ir.config_parameter'].sudo().get_bool(f"l10n_co_edi_demo_mode_{company.id}")

    def _inverse_l10n_co_edi_demo_mode(self):
        for company in self:
            self.env['ir.config_parameter'].sudo().set_bool(f"l10n_co_edi_demo_mode_{company.id}", company.l10n_co_edi_demo_mode)

    def _inverse_l10n_co_edi_test_environment(self):
        for company in self:
            if company.l10n_co_edi_test_environment:
                company.l10n_co_edi_demo_mode = False
