# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def uninstall_hook(env):
    env['pos.config'].search([('use_iot_box', '=', True)]).use_iot_box = False
