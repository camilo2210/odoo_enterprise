from odoo import Command, api, fields, models


class QualityCheck(models.Model):
    _inherit = 'quality.check'

    l10n_tr_response_line_ids = fields.One2many(
        comodel_name='l10n_tr.edispatch.response.line',
        inverse_name='check_id',
        string="e-Response - Unit Count",
        compute='_compute_l10n_tr_response_line_ids',
        store=True,
        readonly=False,
    )

    @api.depends('test_type', 'picking_id.move_ids')
    def _compute_l10n_tr_response_line_ids(self):
        for check in self:
            commands = []
            if check.test_type == 'unit_count' and check.quality_state == 'none':
                commands = [
                    Command.create({'move_id': move.id})
                    for move in check.picking_id.move_ids - check.l10n_tr_response_line_ids.move_id
                ]
            check.l10n_tr_response_line_ids = commands

    def _is_pass_fail_applicable(self):
        if self.test_type == 'unit_count':
            return True
        return super()._is_pass_fail_applicable()

    def _l10n_tr_apply_counted_quantities(self):
        for check in self.filtered(lambda c: c.test_type == 'unit_count'):
            picking = check.picking_id
            if picking.state in {'done', 'cancel'}:
                continue
            for line in check.l10n_tr_response_line_ids:
                if line.move_id.picking_id == picking:
                    line.move_id.quantity = line.received_qty

    def do_pass(self):
        res = super().do_pass()
        self._l10n_tr_apply_counted_quantities()
        return res

    def do_fail(self):
        res = super().do_fail()
        self._l10n_tr_apply_counted_quantities()
        return res

    def _l10n_tr_get_response_payload(self):
        """Return the DespatchAnswerLines entries for this check."""
        payload = []
        for index, line in enumerate(self.l10n_tr_response_line_ids):
            values = {
                'Index': index,
                'Received': line._l10n_tr_get_quantity_payload(line.received_qty),
                'Short': line._l10n_tr_get_quantity_payload(line.missing_qty),
                'Rejected': line._l10n_tr_get_quantity_payload(line.rejected_qty),
                'Oversupply': line._l10n_tr_get_quantity_payload(line.excess_qty),
            }
            optional_values = {
                'RejectReason': line.rejection_reason,
                'SellerCode': line.product_id.default_code,
                'Name': line.product_id.name,
                'Description': line.move_id.description_picking,
            }
            values.update({key: value for key, value in optional_values.items() if value})
            # A price of zero is one GİB can be told; no price at all is left out.
            if (price := line._l10n_tr_get_unit_price()) is not None:
                values['QuantityPrice'] = price
                values['LineTotal'] = price * line.received_qty
            payload.append(values)
        return payload

    def _l10n_tr_is_full_acceptance(self):
        """True when every line arrived complete, undamaged and without excess."""
        return all(
            line.uom_id.is_zero(line.rejected_qty)
            and line.uom_id.is_zero(line.missing_qty)
            and line.uom_id.is_zero(line.excess_qty)
            for line in self.l10n_tr_response_line_ids
        )
