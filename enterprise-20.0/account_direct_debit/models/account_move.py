from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import SQL


class AccountMove(models.Model):
    _inherit = 'account.move'

    has_usable_mandate = fields.Boolean(
        compute='_compute_has_usable_mandate',
        compute_sql='_compute_sql_has_usable_mandate',
        compute_sudo=True,
    )

    def _compute_sql_has_usable_mandate(self, table):
        mandates = table._model.sudo().env['account.direct.debit.mandate']._search(
            Domain('state', '=', 'active')
            & Domain.custom(to_sql=lambda mandate: SQL("%s = %s", mandate.company_id, table.company_id))
            & Domain.custom(to_sql=lambda mandate: SQL("%s = %s", mandate.partner_id, table.commercial_partner_id))
            & Domain.custom(to_sql=lambda mandate: SQL("%s <= %s", mandate.start_date, table.invoice_date))
            & Domain.custom(to_sql=lambda mandate: SQL(
                "(%(end_date)s IS NULL OR %(end_date)s >= %(invoice_date)s)",
                end_date=mandate.end_date,
                invoice_date=table.invoice_date,
            ))
        )
        return SQL(
            "(%(move_type)s IN ('out_invoice', 'in_refund') AND EXISTS %(mandates)s)",
            move_type=table.move_type,
            mandates=mandates.subselect(),
        )

    @api.depends('company_id', 'commercial_partner_id', 'invoice_date')
    def _compute_has_usable_mandate(self):
        for move in self:
            move.has_usable_mandate = bool(move._get_usable_mandate())

    def _get_usable_mandate(self, mandate_type=None):
        """ Returns the first mandate found that can be used to pay this invoice,
        or an empty recordset if there is no such mandate.
        """
        if not self.is_inbound():
            return self.env['account.direct.debit.mandate']
        return self.env['account.direct.debit.mandate']._get_usable_mandate(
            self.company_id.id,
            self.commercial_partner_id.id,
            self.invoice_date,
            mandate_type=mandate_type,
        )

    def _track_log_get_default_subtype(self, track_init_values):
        # OVERRIDE to log a different message when an invoice is paid using a direct debit mandate.
        self.ensure_one()
        if ('payment_state' in track_init_values
            and self.payment_state in ('in_payment', 'paid')
            and self.is_inbound()
            and any(p.mandate_id for p in self.matched_payment_ids)):
            return self.env.ref('account_direct_debit.mt_invoice_paid_with_mandate')
        return super()._track_log_get_default_subtype(track_init_values)
