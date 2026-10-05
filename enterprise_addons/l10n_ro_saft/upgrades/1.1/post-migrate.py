from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Update SAF-T tax codes for 21% and 11% VAT rates with the new ANAF codes
    for company in env['res.company'].search([('chart_template', '=', 'ro'), ('parent_id', '=', False)]):
        Template = env['account.chart.template'].with_company(company)
        Template._load_data({'account.tax': Template._get_ro_saft_account_tax()})
