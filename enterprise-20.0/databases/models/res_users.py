from odoo import fields, models
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    database_user_ids = fields.One2many(comodel_name='databases.user', inverse_name='local_user_id')

    def action_remove_from_all_database(self):
        self.ensure_one()
        if not self.database_user_ids:
            raise UserError(self.env._("This user has no access to remove."))
        return self.database_user_ids.project_id.action_database_remove_users(self.ids)
