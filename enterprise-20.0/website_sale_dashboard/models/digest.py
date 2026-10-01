# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class DigestDigest(models.Model):
    _inherit = 'digest.digest'

    def _get_kpi_custom_settings(self, company, user):
        res = super()._get_kpi_custom_settings(company, user)
        menu_id = self.env.ref('website.menu_website_configuration').id
        res['kpi_action']['kpi_website_sale_total'] = f'website_sale_dashboard.sale_dashboard?menu_id={menu_id}'
        return res
