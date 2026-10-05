# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizards
from . import controllers
from . import report


def _l10n_ke_hr_payroll_post_install(env):
    env.ref('base.ke')._adapt_work_entry_types_to_country()
