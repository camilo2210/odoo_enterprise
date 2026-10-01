from odoo import fields, models
from odoo.fields import Domain
from ast import literal_eval


class MarketingCampaign(models.Model):
    _inherit = "marketing.campaign"

    enroll_action_type = fields.Selection(selection_add=[('page_visit', 'Page Visited'), ('form_submit', 'Form Submitted')])
    website_page_ids = fields.Many2many("website.page", string="Pages")

    @property
    def _ENROLL_ACTION_FIELDS_TO_RESET(self):
        return super()._ENROLL_ACTION_FIELDS_TO_RESET | {'website_page_ids'}

    def _get_campaign_cron_synchronize_enroll_domain(self):
        return super()._get_campaign_cron_synchronize_enroll_domain() | (
            Domain('enroll_type', '=', 'action') & Domain('enroll_action_type', '=', 'page_visit')
        )

    def _get_campaign_domain(self):
        self.ensure_one()
        page_visit_campaigns = self.filtered_domain([('enroll_type', '=', 'action'), ('enroll_action_type', '=', 'page_visit')])
        if not page_visit_campaigns:
            return super()._get_campaign_domain()
        if not self.sudo().website_page_ids:
            return Domain.FALSE

        # TDE note: rewrite to be more efficient
        # TDE note 2: acccess issue to investigate on website.page model
        RecordModel = self.env[page_visit_campaigns.model_id.model]

        tracks = self.env['website.track'].sudo().search([
            ('page_id', 'in', self.sudo().website_page_ids.ids)]
        )
        partners = tracks.visitor_id.partner_id.filtered_domain(literal_eval(self.enroll_domain or '[]'))

        if page_visit_campaigns.model_id.model == 'res.partner':
            partner_domain = [('id', 'in', partners.ids)]
        else:
            partner_fields = RecordModel._mail_get_partner_fields(True)
            partner_domain = Domain.OR([
                Domain(field, 'any', [('id', 'in', partners.ids)])for field in partner_fields
            ])
        return partner_domain
