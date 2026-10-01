from odoo import models
from odoo.fields import Domain


class MailingList(models.Model):
    _inherit = "mailing.list"

    def _post_subscribe_hook(self, contacts_in, contacts_out):
        """
            Inherit to add marketing campaign enroll capability based on mailing list subscription
        """
        super()._post_subscribe_hook(contacts_in, contacts_out)
        if not contacts_in and not contacts_out:
            return
        CampaignSu = self.env["marketing.campaign"].sudo()
        impacted_campaigns = CampaignSu.search(
            CampaignSu._get_campaign_cron_alive_domain() &
            Domain([
                ('enroll_type', '=', 'action'),
                ('enroll_action_type', '=', 'subscribe'),
                ('mailing_list_ids', 'any', [('id', 'in', self.ids)])
            ])
        )
        if not impacted_campaigns:
            return
        impacted_campaigns._add_participants_manually_from_partners(contacts_in.partner_id.ids)
        impacted_campaigns._remove_participants_manually_from_partners(contacts_out.partner_id.ids)
