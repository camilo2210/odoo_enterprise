# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models


def setup_provider(env, code, **kwargs):
    env['platform.order.provider']._setup_provider(code, **kwargs)


def reset_platform_provider(env, code, **kwargs):
    env['platform.order.provider']._remove_provider(code, **kwargs)
