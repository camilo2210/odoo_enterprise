# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def _l10n_uz_hr_payroll_post_install(env):
    env.ref('base.uz')._adapt_work_entry_types_to_country()
