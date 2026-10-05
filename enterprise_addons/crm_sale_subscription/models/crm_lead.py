from ast import literal_eval

from odoo import models, _, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    subscription_count = fields.Integer(compute='_compute_subscription_count', string='Subscriptions')

    @api.depends('partner_id')
    def _compute_subscription_count(self):
        """ Compute the number of subscriptions linked to the lead's customer. """
        if not self:
            return
        self.subscription_count = 0
        domain = self._get_customer_subscriptions_domain()
        orders = self.env['sale.order'].search(domain)
        orders_by_opportunity = orders.grouped('opportunity_id')
        subscription_orders_by_company = orders.filtered('is_subscription').grouped(
            lambda order: order.partner_id.commercial_partner_id
        )

        for lead in self:
            opportunity_subscriptions = orders_by_opportunity.get(lead, self.env['sale.order'])
            # Subscriptions for the same commercial entity, regardless of which opportunity.
            opportunity_company_subscriptions = subscription_orders_by_company.get(
                lead.partner_id.commercial_partner_id, self.env['sale.order'],
            )
            lead.subscription_count = len(opportunity_subscriptions | opportunity_company_subscriptions)

    def _get_customer_subscriptions_domain(self):
        """ Return the domain for all subscriptions, upsells, and renewals for the lead's commercial partner hierarchy. """
        commercial_partner_ids = self.partner_id.commercial_partner_id.ids
        domain = [('subscription_state', 'in', ['7_upsell', '2_renewal']), ('opportunity_id', 'in', self.ids)]
        if commercial_partner_ids:
            domain = fields.Domain.OR([
                domain,
                [('is_subscription', '=', True), ('partner_id.commercial_partner_id', 'in', commercial_partner_ids)]
            ])
        return domain

    def action_open_subscriptions(self):
        """ Open the subscription(s) for the lead's customer, redirecting directly to form if only one. """
        self.ensure_one()
        domain = self._get_customer_subscriptions_domain()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'sale_subscription.sale_subscription_action'
        )
        ctx = action.get('context') or {}
        if isinstance(ctx, str):
            ctx = literal_eval(ctx)
        action['context'] = {**ctx, 'default_opportunity_id': self.id}
        subscriptions = self.env['sale.order'].search(domain)
        if len(subscriptions) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = subscriptions.id
        else:
            action['domain'] = domain
            action.pop('res_id', None)
        return action

    def _update_revenues_from_so(self, order):
        for opportunity in self:
            log_body = ''

            if ((opportunity.expected_revenue or 0) < order.non_recurring_total
                and order.currency_id == opportunity.company_id.currency_id
            ):
                opportunity.expected_revenue = order.non_recurring_total
                log_body = _("Expected revenue has been updated based on the linked Sales orders.")

            if ((opportunity.recurring_revenue_monthly or 0) < order.recurring_monthly
                and order.currency_id == opportunity.company_id.currency_id
            ):
                if not opportunity.recurring_plan:
                    opportunity.recurring_plan = opportunity.env.ref('crm.crm_recurring_plan_monthly', raise_if_not_found=False)
                opportunity.recurring_revenue = order.recurring_monthly * (opportunity.recurring_plan.number_of_months or 1)
                if self.env.user.has_group("crm.group_use_recurring_revenues"):
                    if log_body:
                        log_body = _("Recurring revenue and Expected revenue have been updated based on the linked Sales Orders.")
                    else:
                        log_body = _("Recurring revenue has been updated based on the linked Sales Orders.")
            if log_body:
                opportunity._track_set_log_message(log_body)
