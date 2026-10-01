# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import SQL, split_every


class Website(models.Model):
    _inherit = 'website'

    wa_sale_template_id = fields.Many2one('whatsapp.template', domain=[('model', '=', 'sale.order'), ('status', '=', 'approved')])
    wa_sale_cart_recovery_template_id = fields.Many2one(
        'whatsapp.template',
        domain=[('model', '=', 'sale.order'), ('status', '=', 'approved')]
    )
    send_abandoned_cart_whatsapp_activation_time = fields.Datetime(
        string="Time when the 'Send abandoned cart' feature was activated for WhatsApp followup.",
        compute="_compute_send_abandoned_cart_whatsapp_activation_time",
        store=True,
    )

    def write(self, vals):
        res = super().write(vals)
        if "send_abandoned_cart_followup" in vals or "wa_sale_cart_recovery_template_id" in vals:
            self._toggle_abandoned_cart_whatsapp_cron()
        return res

    @api.depends("send_abandoned_cart_followup", "wa_sale_cart_recovery_template_id")
    def _compute_send_abandoned_cart_whatsapp_activation_time(self):
        for website in self:
            if website.send_abandoned_cart_followup and website.wa_sale_cart_recovery_template_id:
                website.send_abandoned_cart_whatsapp_activation_time = fields.Datetime.now()

    @api.model
    def _toggle_abandoned_cart_whatsapp_cron(self):
        """ Enable the abandoned cart WhatsApp cron if the feature is enabled on some website,
        disable it otherwise. """
        cron = self.env.ref('whatsapp_website_sale.ir_cron_send_abandoned_cart_whatsapp', raise_if_not_found=False)
        if not cron:
            return
        cron.sudo().active = bool(self.sudo().search_count([
            ('send_abandoned_cart_followup', '=', True),
            ('wa_sale_cart_recovery_template_id', '!=', False),
        ], limit=1))

    @api.model
    def _cron_send_abandoned_cart_whatsapp(self):
        website_domain = (
            Domain([("send_abandoned_cart_followup", "=", True), ("wa_sale_cart_recovery_template_id", "!=", False)])
        )

        all_abandoned_carts = self.env["sale.order"]._read_group(
            Domain([
                ("is_abandoned_cart", "=", True),
                ("website_id", "in", website_domain),
                ("cart_recovery_whatsapp_sent", "=", False),
            ])
            & Domain.custom(
                to_sql=lambda table: SQL(
                    "%s >= %s",
                    table.date_order,
                    table._join("website_id").send_abandoned_cart_whatsapp_activation_time,
                )
            ),
            groupby=["website_id"],
            aggregates=["id:recordset", "id:count"],
        )
        if not all_abandoned_carts:
            return

        self.env["ir.cron"]._commit_progress(
            remaining=sum(count for _website, _cart, count in all_abandoned_carts)
        )

        for _website, cart_group, _count in all_abandoned_carts:
            abandoned_carts = cart_group._filter_can_send_abandoned_cart_followup().filtered('partner_id.phone')
            failed_carts = cart_group - abandoned_carts
            failed_carts.write({'cart_recovery_whatsapp_sent': True})
            self.env["ir.cron"]._commit_progress(len(failed_carts))
            for carts_batch in split_every(10, abandoned_carts.ids, self.env["sale.order"].browse):
                carts_batch._cart_recovery_whatsapp_send()
                self.env["ir.cron"]._commit_progress(len(carts_batch))

    @api.model
    def _get_settings_to_copy_onto_new_default_website(self):
        """ Provides a list of settings that should always be set on the default
        website. When the default website changes, a check is performed. If some
        of these settings are not already set on the new default website, they
        are copied from the previous default website."""
        return super()._get_settings_to_copy_onto_new_default_website() + ['wa_sale_template_id']
