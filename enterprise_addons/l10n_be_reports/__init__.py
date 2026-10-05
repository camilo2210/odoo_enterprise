# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models
from . import wizard
from . import report


def _l10n_be_reports_post_init(env):
    env['res.company'].search([])._compute_l10n_be_region_id()
