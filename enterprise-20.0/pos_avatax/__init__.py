from . import models


def uninstall_hook(env):
    env['pos.config'].search([('module_pos_avatax', '=', True)]).module_pos_avatax = False
