# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizards


def _l10n_au_hr_payroll_post_install(env):
    env.ref('base.au')._adapt_work_entry_types_to_country()
