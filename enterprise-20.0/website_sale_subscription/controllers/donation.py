from odoo.addons.website_sale.controllers.donation import WebsiteSaleDonation


class WebsiteSaleSubscriptionDonation(WebsiteSaleDonation):

    def _get_extra_donation_info(self):
        info = super()._get_extra_donation_info()
        recurring_product = self.env.ref(
            "website_sale_subscription.product_recurring_donation", raise_if_not_found=False
        )
        if not recurring_product:
            return info
        # Unpublished, sudo to allow public users to read it
        recurring_product_sudo = recurring_product.sudo()
        plan_ids = recurring_product_sudo.subscription_rule_ids.plan_id
        info.update({
            "recurring_product_template_id": recurring_product_sudo.id,
            "recurring_product_id": recurring_product_sudo.product_variant_id.id,
            "plans": [{"id": plan.id, "name": plan.name} for plan in plan_ids],
        })
        return info
