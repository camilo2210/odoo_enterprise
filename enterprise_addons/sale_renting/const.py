# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)

PERIODICITY_LABEL_SINGULAR = {
    "hours": _lt("Hour"),
    "days": _lt("Day"),
    "nights": _lt("Night"),
    "weeks": _lt("Week"),
}

PERIODICITY_LABEL = {
    "hours": _lt("Hours"),
    "days": _lt("Days"),
    "nights": _lt("Nights"),
    "weeks": _lt("Weeks"),
}

SECONDS_IN_PERIODICITY = {
    "hours": 3600,
    "days": 24 * 3600,
    "nights": 24 * 3600,
    "weeks": 7 * 24 * 3600,
}
