from odoo import fields, models

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner"]

    commercial_partner_opportunity_count = fields.Integer(
        related="commercial_partner_id.opportunity_count",
        string="Commercial Partner Opportunity Count",
        groups="sales_team.group_sale_salesman",
        related_sudo=False,
    )

    def get_view_opportunities_action(self, phone=None):
        """
        Get an action to view or create opportunities for a partner.

        When no partner is provided:
        - Returns an action to create a new opportunity with the given phone number.

        When a partner is provided:
        - Uses the commercial partner(company) to find opportunities.
        - If no opportunities exist: returns a form action to create a new opportunity.
        - If one opportunity exists: returns the form view of that opportunity.
        - If multiple opportunities exist: returns a list view with domain filter.
        - All views include filters for won, ongoing, and lost opportunities.

        :param phone: Optional phone number for creating a new opportunity without a partner.
        :return: window action dictionary configured for viewing/creating opportunities.
        """
        action = self.env["ir.actions.act_window"]._for_xml_id("crm.crm_lead_opportunities")
        if not self:  # If no partner is provided, we create a new opportunity for the phone.
            action["views"] = [[False, "form"]]
            action["context"] = {
                "default_phone": phone,
            }
            return action
        self.ensure_one()
        commercial_partner = self.commercial_partner_id
        action["context"] = {
            "search_default_filter_won": True,
            "search_default_filter_ongoing": True,
            "search_default_filter_lost": True,
            "active_test": False,
        }
        if commercial_partner.opportunity_count == 0:
            action["views"] = [[False, "form"]]
            action["context"]["default_partner_id"] = self.id
            return action
        domain = commercial_partner._get_contact_opportunities_domain()
        if commercial_partner.opportunity_count == 1:
            action["views"] = [[False, "form"]]
            action["res_id"] = self.env["crm.lead"].with_context(active_test=False).search(domain, limit=1).id
        else:
            action["domain"] = domain
        return action

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)
        has_access = (
            self.has_field_access(self._fields["commercial_partner_opportunity_count"], "read") and
            self.env["crm.lead"].has_access("read")
        )
        if has_access:
            res.attr("commercial_partner_opportunity_count")
