from odoo import api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _inherit = "res.partner"

    ticket_ids = fields.One2many("helpdesk.ticket", "partner_id")
    commercial_partner_open_ticket_count = fields.Integer(compute="_compute_commercial_partner_open_ticket_count", groups="helpdesk.group_helpdesk_user")
    commercial_partner_ticket_count = fields.Integer(
        related="commercial_partner_id.ticket_count",
        string="Commercial Partner Ticket Count",
        groups="helpdesk.group_helpdesk_user",
        related_sudo=False,
    )

    @api.depends("ticket_ids.fold")
    def _compute_commercial_partner_open_ticket_count(self):
        commercial_partner_ids = self.commercial_partner_id
        count_by_partner_id = commercial_partner_ids._count_tickets_by_partner_id(
            extra_domain=[("fold", "=", False)],
        )
        for partner in self:
            partner.commercial_partner_open_ticket_count = count_by_partner_id.get(partner.commercial_partner_id.id, 0)

    def action_voip_open_tickets(self):
        self.ensure_one()
        return self.commercial_partner_id.action_open_helpdesk_ticket()

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)

        def can_read_commercial_partner_ticket_count(partner):
            try:
                partner.read(["commercial_partner_ticket_count"])
            except AccessError:
                return False
            return True

        res.attr("commercial_partner_ticket_count", predicate=can_read_commercial_partner_ticket_count)
