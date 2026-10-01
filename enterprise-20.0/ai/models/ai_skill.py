# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AISkill(models.Model):
    _name = 'ai.skill'
    _description = "Create a skill that leverages instructions and tools to direct Odoo AI in assisting the user with their tasks."
    _explanation = "Represents a specific task or skill for the AI, providing instructions and tools to guide the assistant's behavior for a particular domain."

    name = fields.Char(string="Title", required=True)
    description = fields.Text(string="Description")
    instructions = fields.Text(string="Instructions")
    tool_ids = fields.Many2many('ir.actions.server', string="AI Tools", domain=[('use_in_ai', '=', True)], groups='base.group_system')
    type = fields.Char(string="Type", store=False, compute="_compute_type")
    is_native_skill = fields.Boolean(default=False, readonly=True, copy=False, help="Built-in skill with fixed behavior that cannot be edited.")

    @api.depends("tool_ids")
    def _compute_type(self):
        for skill in self:
            skill.type = "executable" if skill.sudo().tool_ids else "guidance"

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('install_mode') and any(vals.get('is_native_skill') for vals in vals_list):
            raise ValidationError(self.env._("Native skills cannot be created."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('install_mode') and (vals.get('is_native_skill') or self.filtered('is_native_skill')):
            raise ValidationError(self.env._("Native skills cannot be modified."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_native_skills(self):
        if not self.env.context.get('force_delete') and any(skill.is_native_skill for skill in self):
            raise ValidationError(self.env._("Native skills cannot be deleted."))
