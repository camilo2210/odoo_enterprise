# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import SQL


class MailingMailing(models.Model):
    _inherit = 'mailing.mailing'

    @api.model
    def default_get(self, fields):
        vals = super().default_get(fields)
        if 'subject' in fields and self.env.context.get('default_use_in_marketing_automation', False):
            vals['subject'] = self.env.context.get('default_name')
        return vals

    use_in_marketing_automation = fields.Boolean(
        string='Specific mailing used in marketing campaign', default=False,
        help='Marketing campaigns use mass mailings with some specific behavior; this field is used to indicate its statistics may be suspicious.')
    marketing_activity_ids = fields.One2many('marketing.activity', 'mass_mailing_id', string='Marketing Activities', copy=False)

    # TODO: remove in master
    def convert_links(self):
        """Override convert_links so we can add marketing automation campaign instead of mass mail campaign"""
        res = {}
        done = self.env['mailing.mailing']
        for mass_mailing in self:
            if self.env.context.get('default_marketing_activity_id'):
                activity = self.env['marketing.activity'].browse(self.env.context['default_marketing_activity_id'])
                vals = {
                    'mass_mailing_id': mass_mailing.id,
                    'campaign_id': activity.campaign_id.utm_campaign_id.id,
                    'medium_id': mass_mailing.medium_id.id,
                    'source_id': mass_mailing.source_id.id,
                    'utm_reference': f'{activity._name},{activity.id}',
                }
                res[mass_mailing.id] = mass_mailing._shorten_links(
                    mass_mailing.body_html or '',
                    vals,
                    blacklist=['/unsubscribe_from_list', '/view']
                )
                done |= mass_mailing
        res.update(super(MailingMailing, self - done).convert_links())
        return res

    def _get_link_tracker_values(self):
        res = super()._get_link_tracker_values()
        if self.env.context.get('default_marketing_activity_id'):
            activity = self.env['marketing.activity'].browse(self.env.context['default_marketing_activity_id'])
            res['campaign_id'] = activity.campaign_id.utm_campaign_id.id
            res['utm_reference'] = f'{activity._name},{activity.id}'
        return res

    def _get_seen_list_extra(self, query):
        query.add_where(SQL("%s IS NOT TRUE", query.table.marketing_trace_id.is_test))

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_linked_activities(self):
        protected = self.filtered(lambda m: m.marketing_activity_ids)
        if protected:
            raise UserError(
                _("Mailings %(mailing_names)s are used in marketing campaigns. You should take care of this before unlinking the mailings.",
                  mailing_names=", ".join(protected.mapped("display_name"))
                )
            )

    def action_retry_failed(self, extra_domain=None):
        """
        Prevent retrying mailings tied to marketing automation.
        Retrying bypasses the automation filters and targets the entire model.
        """
        if self.filtered('use_in_marketing_automation'):
            raise UserError(_(
                "Oops! You can't retry sending emails from inside a Marketing Automation campaign."
            ))

        return super().action_retry_failed(extra_domain=extra_domain)
