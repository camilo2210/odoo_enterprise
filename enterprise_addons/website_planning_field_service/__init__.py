from . import controllers
from . import models


def uninstall_hook(env):
    env['res.company'].sudo().search(
        [('website_planning_field_service', '=', True)]
    ).website_planning_field_service = False
