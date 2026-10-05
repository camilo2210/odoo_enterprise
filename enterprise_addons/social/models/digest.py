# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Digest(models.Model):
    _inherit = 'digest.digest'

    kpi_nbr_of_clicks = fields.Boolean('Social Media Clicks')
    kpi_nbr_of_clicks_value = fields.Integer(
        compute='_compute_kpi_nbr_of_clicks_value'
    )

    def _compute_kpi_nbr_of_clicks_value(self):
        self._raise_if_not_member_of('social.group_social_manager')
        start, end, companies = self._get_kpi_compute_parameters()
        self.env.cr.execute("""
            SELECT account.company_id, COUNT(DISTINCT(click.id))
              FROM link_tracker_click click
        INNER JOIN link_tracker link ON link.id = click.link_id
        INNER JOIN social_post post ON link.utm_reference = CONCAT('social.post,', post.id)
        INNER JOIN social_account_social_post_rel account_post ON account_post.social_post_id = post.id
        INNER JOIN social_account account ON account.id = account_post.social_account_id
        WHERE account.company_id IN %(company_ids)s AND click.create_date >= %(start)s AND click.create_date < %(end)s
          GROUP BY account.company_id
        """, params={'company_ids': tuple(companies.ids), 'start': start, 'end': end})
        Company = self.env['res.company']
        values_per_company = {Company.browse(company_id): value for company_id, value in self.env.cr.fetchall()}
        for digest in self:
            company = digest.company_id or self.env.company
            digest.kpi_nbr_of_clicks_value = values_per_company.get(company, 0)

    def _get_kpi_custom_settings(self, company, user):
        res = super()._get_kpi_custom_settings(company, user)
        menu_id = self.env.ref('social.menu_social_global').id
        res['kpi_action']['kpi_nbr_of_clicks'] = f'social.action_social_post_pivot?menu_id={menu_id}'
        res['kpi_sequence']['kpi_nbr_of_clicks'] = 14500
        return res
