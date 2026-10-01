

def urbanpiper_post_init(env):
    en_US_language = env['res.lang'].with_context(active_test=False).sudo().search([('code', '=', 'en_US')], limit=1)
    if not en_US_language:
        env['base.language.install'].create({'lang_ids': [(6, 0, en_US_language.ids)]}).lang_install()
    if not en_US_language.active:
        en_US_language.active = True
