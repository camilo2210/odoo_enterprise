from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    esg_nace_id = fields.Many2one('esg.nace')
    esg_company_size = fields.Selection(
        selection=[
            ('small', '< 250 employees'),
            ('medium', '250 - 1000 employees'),
            ('large', '> 1000 employees'),
        ],
    )
    esg_revenues_value = fields.Monetary(currency_field='currency_id')
    esg_assets_value = fields.Monetary(currency_field='currency_id')
    esg_core_business_description = fields.Html()
