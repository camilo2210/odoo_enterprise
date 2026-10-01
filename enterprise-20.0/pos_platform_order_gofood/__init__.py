# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
from . import utils

from odoo.addons.pos_platform_order import setup_provider, reset_platform_provider


def post_init_hook(env):
    setup_provider(env, 'gofood')


def uninstall_hook(env):
    reset_platform_provider(env, 'gofood')
