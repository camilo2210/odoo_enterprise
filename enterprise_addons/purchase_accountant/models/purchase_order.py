from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    accrual_move_ids = fields.Many2many(
        comodel_name='account.move',
        compute='_compute_accrual_move_ids',
        string="Accrual Entries",
    )
    accrual_move_count = fields.Integer(compute='_compute_accrual_move_ids')

    @api.depends('order_line.accrual_move_ids')
    def _compute_accrual_move_ids(self):
        if not self.env.user.has_group('account.group_account_user'):
            self.accrual_move_ids = False
            self.accrual_move_count = 0
            return
        for order in self:
            order.accrual_move_ids = order.order_line.accrual_move_ids
            order.accrual_move_count = len(order.accrual_move_ids)

    def action_open_accrual_moves(self):
        self.ensure_one()
        return {
            'name': _("Accrual Entries"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.accrual_move_ids.ids)],
        }
