from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    appointment_type_ids = fields.Many2many('appointment.type', string="Available in",
        relation="appointment_type_res_users_rel",
        domain="[('schedule_based_on', '=', 'users')]")

    @api.ondelete(at_uninstall=False)
    def _unlink_related_appointment_leaves(self):
        """ Unlink related appointment leaves if all their users have been unlinked.
        This prevents having 'users' appointment leaves set on no user.
        """
        leaves = self.env['appointment.leave'].sudo().search([('user_ids', 'in', self.ids)])
        leaves.filtered(lambda leave: leave.user_ids and not (leave.user_ids - self)).unlink()
