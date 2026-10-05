from odoo import api, fields, models


class DatabasesUser(models.Model):
    _description = "Database User"
    _name = 'databases.user'

    project_id = fields.Many2one('project.project', string="Database", ondelete='cascade', index='btree',
                                 required=True, domain=[('database_hosting', '!=', False)])
    name = fields.Char(required=True, index='trigram')
    login = fields.Char(required=True, index='trigram')
    latest_authentication = fields.Datetime(readonly=True)
    local_user_id = fields.Many2one(
        comodel_name='res.users',
        compute='_compute_local_user_id',
        search='_search_local_user_id',
    )

    @api.depends('login')
    def _compute_local_user_id(self):
        local_users_by_login = dict(self.env['res.users'].with_context(active_test=False)._read_group(
            [('login', 'in', self.mapped('login'))],
            ['login'],
            ['id:recordset']
        ))
        for db_user in self:
            db_user.local_user_id = local_users_by_login.get(db_user.login, False)

    def _search_local_user_id(self, operator, value):
        if operator != 'in':  # other operator are automatically derived from it by the ORM
            return NotImplemented
        logins = self.env['res.users'].browse(value).mapped('login')
        return fields.Domain('login', operator, logins)

    def action_invite_users(self):
        if not self.project_id:
            active_id = self.env.context.get('active_id')
            return self.project_id.browse(active_id).action_database_invite_users()
        return self.project_id.action_database_invite_users()

    def action_remove_users(self):
        return self.project_id.action_database_remove_users(self.local_user_id.ids)
