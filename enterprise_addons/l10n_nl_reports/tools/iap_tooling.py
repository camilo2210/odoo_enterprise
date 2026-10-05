DEFAULT_IAP_ENDPOINT = 'https://l10n-nl-sbr.api.odoo.com'
TEST_IAP_ENDPOINT = 'https://l10n-nl-sbr.test.odoo.com'
SBR_MODE_PARAM = 'l10n_nl_reports.sbr_mode'


def is_test_mode(env):
    return env['ir.config_parameter'].sudo().get_str(SBR_MODE_PARAM, 'prod') == 'test'


def get_iap_endpoint(env):
    return TEST_IAP_ENDPOINT if is_test_mode(env) else DEFAULT_IAP_ENDPOINT
