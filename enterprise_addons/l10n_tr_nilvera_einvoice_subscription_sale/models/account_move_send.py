import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    # -------------------------------------------------------------------------
    # ALERTS
    # -------------------------------------------------------------------------

    def _get_alerts(self, moves, moves_data):
        alerts = super()._get_alerts(moves, moves_data)

        if tr_invalid_subscription_dates := moves.filtered(lambda move: move._l10n_tr_nilvera_einvoice_check_invalid_subscription_dates()):
            alerts["tr_invalid_subscription_dates"] = {
                'level': 'danger',
                "message": _("The following invoice(s) need to have the same Start Date and End Date on all their respective Subscription Product Invoice Lines."),
                "action_text": _("View Invoice(s)"),
                "action": tr_invalid_subscription_dates._get_records_action(name=_("Check data on Invoice(s)")),
            }

        return alerts
