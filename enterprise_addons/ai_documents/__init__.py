# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def uninstall_hook(env):
    env["base.automation"].search([("ai_autosort_folder_id", "!=", False)]).unlink()
