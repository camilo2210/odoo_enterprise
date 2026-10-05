from odoo.addons.website.controllers.form import WebsiteForm
from odoo.fields import Domain


class MarketingAutomationWebsiteForm(WebsiteForm):

    def insert_record(self, request, model, *args, **kwargs):
        record_id = super().insert_record(request, model, *args, **kwargs)
        if not record_id:
            return record_id
        CampaignSu = request.env["marketing.campaign"].sudo()
        impacted_campaigns = CampaignSu.search(
            CampaignSu._get_campaign_cron_alive_domain() & Domain(
            [
                ("enroll_action_type", "=", "form_submit"),
                ("enroll_type", "=", "action"),
                ("model_id", "=", model.id),
            ]
        ))
        if impacted_campaigns:
            impacted_campaigns.action_add_participants_manually(model.model, record_id)
        return record_id
