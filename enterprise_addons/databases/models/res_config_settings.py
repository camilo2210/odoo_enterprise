from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    databases_apikey = fields.Char(
        string="Odoo.com API Key",
        config_parameter="databases.odoocom_apikey",
        groups='base.group_system',
    )
    databases_project_template_id = fields.Many2one(
        'project.project',
        domain=[('is_template', '=', True)],
        string="Project template",
        config_parameter="databases.odoocom_project_template",
        groups='base.group_system',
    )
    # TODO: merge module and convert into a classic config_param in master
    databases_saas_single_sign_on = fields.Boolean(
        string="Saas SSO",
        config_parameter="databases.saas_single_sign_on",
        default=False,
        compute='_compute_databases_saas_single_sign_on',
        inverse='_inverse_databases_saas_single_sign_on',
        groups='base.group_system',
    )
    module_databases_auth = fields.Boolean(compute='_compute_module_auth_oauth_status')

    def _compute_databases_saas_single_sign_on(self):
        self.databases_saas_single_sign_on = self.env['ir.config_parameter'].sudo().get_bool('databases.saas_single_sign_on', False)

    def _inverse_databases_saas_single_sign_on(self):
        sso = any(self.mapped('databases_saas_single_sign_on'))
        if sso != self.env['ir.config_parameter'].sudo().get_bool('databases.saas_single_sign_on', False):
            self.env['ir.config_parameter'].sudo().set_bool('databases.saas_single_sign_on', sso)

    @api.depends('databases_saas_single_sign_on')
    def _compute_module_auth_oauth_status(self):
        self.module_databases_auth = (
            'databases_auth' in self.env['ir.module.module']._installed()
            or any(self.mapped('databases_saas_single_sign_on'))
        )
