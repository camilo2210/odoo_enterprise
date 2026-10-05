from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    zkteco_checkin_id = fields.Char(string="ZKTeco Check-in ID")
    zkteco_checkout_id = fields.Char(string="ZKTeco Check-out ID")
    zkteco_checkin_transaction_id = fields.Many2one("zkteco.transactions", readonly=True)
    zkteco_checkout_transaction_id = fields.Many2one("zkteco.transactions", readonly=True)

    in_mode = fields.Selection(selection_add=[("biotime", "Biotime")])
    out_mode = fields.Selection(selection_add=[("biotime", "Biotime")])
    terminal_id = fields.Many2one("zkteco.terminal", help="The Biotime terminal in which the record is created from")

    @api.ondelete(at_uninstall=True)
    def _unlink_reset_linked_zkteco_transactions(self):
        if linked_transactions := self.zkteco_checkin_transaction_id | self.zkteco_checkout_transaction_id:
            linked_transactions.write({"is_processed": False, "attendance_unlinked": True})
