from . import models
from . import wizard


def _post_init_hook_setup_issuing_demo(env):
    env['ir.config_parameter'].set_str('hr_expense_stripe.stripe_mode', 'test')
