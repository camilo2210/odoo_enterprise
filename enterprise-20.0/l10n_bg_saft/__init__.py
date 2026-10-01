# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models, wizard


def _existing_xmlids(Template, data):
    return {
        xmlid: values
        for xmlid, values in data.items()
        if Template.ref(xmlid, raise_if_not_found=False)
    }


def _add_account_saft_code(env):
    bg_coa_companies = env['res.company'].search([('chart_template', '=', 'bg'), ('parent_id', '=', False)])
    for company in bg_coa_companies:
        Template = env['account.chart.template'].with_company(company)
        data = _existing_xmlids(Template, Template._get_bg_saft_account_code())
        Template._load_data({'account.account': data})


def _update_saft_fields_on_taxes(env):
    bg_coa_companies = env['res.company'].search([('chart_template', '=', 'bg'), ('parent_id', '=', False)])
    for company in bg_coa_companies:
        Template = env['account.chart.template'].with_company(company)
        data = _existing_xmlids(Template, Template._get_bg_saft_account_tax())
        Template._load_data({'account.tax': data})


def post_init_hooks(env):
    _add_account_saft_code(env)
    _update_saft_fields_on_taxes(env)
