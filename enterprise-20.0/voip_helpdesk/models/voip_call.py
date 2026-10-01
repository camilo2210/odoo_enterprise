from odoo import fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"
    _name = "voip.call"

    commercial_partner_ticket_count = fields.Integer(related="partner_id.commercial_partner_ticket_count", groups="helpdesk.group_helpdesk_user", related_sudo=False)
    commercial_partner_open_ticket_count = fields.Integer(related="partner_id.commercial_partner_open_ticket_count", groups="helpdesk.group_helpdesk_user", related_sudo=False)

    def voip_action_open_helpdesk_ticket(self):
        self.ensure_one()
        if self.commercial_partner_ticket_count > 0:
            return self.partner_id.commercial_partner_id.action_open_helpdesk_ticket()
        action = self.env["ir.actions.actions"]._for_xml_id("helpdesk.helpdesk_ticket_action_main_tree")
        action["views"] = [[False, "form"]]
        action.update(
            {
                "context": {
                    "default_partner_phone": self.phone_number,
                    "default_partner_id": self.partner_id.id,
                },
            },
        )
        return action
