from odoo import fields, models

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _inherit = "res.partner"

    commercial_partner_sale_order_count = fields.Integer(
        related="commercial_partner_id.sale_order_count",
        string="Commercial Partner Sale Order Count",
        groups="sales_team.group_sale_salesman",
        related_sudo=False,
    )

    def action_voip_view_sale_orders(self):
        self.ensure_one()
        partner = self.commercial_partner_id
        action = self.env["ir.actions.actions"]._for_xml_id("sale.act_res_partner_2_sale_order")
        action["domain"] = [("partner_id", "child_of", partner.id)]
        action["context"] = {"default_partner_id": partner.id}
        return action

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)
        has_access = (
            self.has_field_access(self._fields["commercial_partner_sale_order_count"], "read") and
            self.env["sale.order"].has_access("read")
        )
        if has_access:
            res.attr("commercial_partner_sale_order_count")
