# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResGroupFunctional(models.Model):
    _name = "res.group.functional"
    _inherit = ["avatar.mixin"]
    _description = "Group Functional"
    _allow_sudo_commands = False

    name = fields.Char(string="Name", required=True)
    user_ids = fields.Many2many("res.users", string="Users")
    responsible_ids = fields.Many2many(
        "res.users",
        "res_group_functional_responsible_id",
        string="Group Responsibles",
        default=lambda self: self.env.user,
        required=True,
        help="Responsibles can update and delete the group.",
        inverse="_inverse_responsible_ids"
    )

    @api.model_create_multi
    def create(self, vals_list):
        groups = super().create(vals_list)
        for group in groups:
            if not group.image_1920:
                group.image_1920 = group._avatar_generate_svg()
        return groups

    def _inverse_responsible_ids(self):
        # Add the responsible as members
        for record in self:
            record.user_ids |= record.responsible_ids
