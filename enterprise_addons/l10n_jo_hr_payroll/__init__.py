# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models


def _l10n_jo_hr_payroll_post_install(env):
    env.ref('base.jo')._adapt_work_entry_types_to_country()
