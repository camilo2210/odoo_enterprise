# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
from . import report
from . import wizard


def uninstall_hook(env):

    def update_action_window(xmlid):
        act_window = env.ref(xmlid, raise_if_not_found=False)
        if act_window and act_window.domain and 'is_accessible_to_current_user' in act_window.domain:
            act_window.domain = []

    update_action_window('hr_recruitment.crm_case_categ0_act_job')
    update_action_window('hr_recruitment.action_hr_job_applications')
