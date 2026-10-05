# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from math import ceil
from typing import Literal

from odoo.addons.sale_renting import const


def number_of_periods(
    periodicity: Literal["hours", "days", "nights", "weeks"], start: datetime, end: datetime
):
    delta = end - start
    return ceil(delta.total_seconds() / const.SECONDS_IN_PERIODICITY[periodicity])
