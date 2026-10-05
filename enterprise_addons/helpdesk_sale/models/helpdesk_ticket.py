from odoo import api, fields, models
from odoo.tools import OrderedSet


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    sale_order_id = fields.Many2one(
        'sale.order', string='Ref. Sales Order',
        domain="""[
            '|', (not commercial_partner_id, '=', 1), ('partner_id', 'child_of', commercial_partner_id or []),
            ('company_id', '=', company_id)]""",
        index='btree_not_null',
    )
    sale_order_state = fields.Selection(related='sale_order_id.state', tracking=False)
    sale_warning_text = fields.Text('Helpdesk Warning', compute='_compute_sale_warning_text', help='Warning for the partner as set by the user.')

    @api.depends('partner_id.name', 'partner_id.sale_warn_msg')
    def _compute_sale_warning_text(self):
        if not self.env.user.has_group("sale.group_warning_sale"):
            self.sale_warning_text = ""
            return
        for ticket in self:
            if not ticket.team_id.use_helpdesk_sale_timesheet:
                ticket.sale_warning_text = ""
                continue
            warnings = OrderedSet()
            if partner_msg := ticket.partner_id.sale_warn_msg:
                warnings.add(
                    (ticket.partner_id.name or ticket.partner_id.display_name) + " - " + partner_msg
                )
            if partner_parent_msg := ticket.partner_id.parent_id.sale_warn_msg:
                parent = ticket.partner_id.parent_id
                warnings.add((parent.name or parent.display_name) + " - " + partner_parent_msg)
            ticket.sale_warning_text = "\n".join(warnings)

    def copy_data(self, default=None):
        if not self.env.user.has_group('sales_team.group_sale_salesman') and not self.env.user.has_group('account.group_account_invoice'):
            if default is None:
                default = {'sale_order_id': False}
            else:
                default.update({'sale_order_id': False})
        return super().copy_data(default=default)
