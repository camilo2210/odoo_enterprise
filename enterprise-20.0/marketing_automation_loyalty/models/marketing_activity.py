from __future__ import annotations

import typing

from odoo import api, exceptions, fields, models, _

if typing.TYPE_CHECKING:
    from odoo.addons.marketing_automation.models.marketing_trace import MarketingTrace


class MarketingActivity(models.Model):
    _inherit = "marketing.activity"

    activity_type = fields.Selection(
        selection_add=[("coupon", "Coupon")], ondelete={"coupon": "cascade"}
    )
    loyalty_program_id = fields.Many2one(
        "loyalty.program", string="Coupon Program",
        compute='_compute_activity_coupon_data', readonly=False, store=True,
        domain=[
            ("program_type", "in", ["coupons", "promo_code", "next_order_coupons"])
        ],
    )
    loyalty_mail_template_id = fields.Many2one(
        "mail.template", string="Mail Template", domain=[("model", "=", "loyalty.card")],
        compute='_compute_activity_coupon_data', readonly=False, store=True,
    )

    @api.constrains('activity_type', 'loyalty_program_id')
    def _check_activity_type_coupon(self):
        activity_coupon = self.filtered(lambda a: a.activity_type == 'coupon')
        for activity in activity_coupon:
            if not activity.loyalty_program_id:
                raise exceptions.ValidationError(_(
                    'A Coupon Program is required for coupon-based activity %(activity_name)s',
                    activity_name=activity.name,
                ))
            if not activity.loyalty_program_id.program_type in {"coupons", "promo_code", "next_order_coupons"}:
                raise exceptions.ValidationError(_(
                    'Coupon Program should be one of Coupons, Discounts or Next Order Coupons on %(activity_name)s',
                    activity_name=activity.name,
                ))

    @api.depends('activity_type')
    def _compute_activity_coupon_data(self):
        to_reset = self.filtered(lambda a: a.activity_type != 'coupon')
        to_reset.loyalty_program_id = False
        to_reset.loyalty_mail_template_id = False

    @api.depends('loyalty_program_id')
    def _compute_name(self):
        # OVERRIDE
        coupon_activities = self.filtered(
            lambda activity: activity.activity_type == 'coupon')
        super(MarketingActivity, self - coupon_activities)._compute_name()
        for activity in coupon_activities:
            activity.name = _(
                "Send Coupon: %(coupon_name)s",
                coupon_name=activity.loyalty_program_id.display_name or '',
            )

    @api.depends('loyalty_program_id')
    def _compute_description(self):
        # OVERRIDE
        coupon_activities = self.filtered("loyalty_program_id")
        super(MarketingActivity, self - coupon_activities)._compute_description()
        for activity in coupon_activities:
            activity.description = activity.loyalty_program_id.display_name

    def _execute_coupon(self, traces: MarketingTrace) -> MarketingTrace:
        """ Execute 'coupon' activity. It mainly consists in invoking the generation
        wizard. Email sending is part of the program. """
        res_ids = traces.mapped("res_id")
        records = self.env[self.model_name].browse(res_ids)

        # find recipient linked to participants
        records_partners = records._mail_get_partners()
        partner_ids = {pid for partners in records_partners.values() for pid in partners.ids}
        generate = self.env["loyalty.generate.wizard"].create(
            {
                "customer_ids": [(6, 0, list(partner_ids))],
                "mode": "selected",
                "program_id": self.loyalty_program_id.id,
            }
        )
        loyalty_cards = generate.generate_coupons()

        # if template on coupon different from program: send an email
        if self.loyalty_mail_template_id and self.loyalty_mail_template_id != self.loyalty_program_id.mail_template_id:
            loyalty_cards.message_mail_with_source(
                self.loyalty_mail_template_id,
                email_layout_xmlid="mail.mail_notification_layout",
            )

        # successful traces -> record has a customer who received a coupon
        recipients = loyalty_cards.partner_id
        success_records = records.filtered(lambda r: records_partners[r.id] & recipients)
        success_traces = traces.filtered(lambda t: t.res_id in success_records.ids)
        success_traces.action_set_processed()
        (traces - success_traces).action_set_error(
            message=_("Coupon could not be sent to the customer")
        )
        return success_traces
