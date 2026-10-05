from odoo import Command, api, fields, models


class QualityCheckWizard(models.TransientModel):
    _inherit = 'quality.check.wizard'

    l10n_tr_count_line_ids = fields.One2many(
        comodel_name='l10n_tr.edispatch.count.line',
        inverse_name='wizard_id',
        string="e-Response - Unit Count",
        compute='_compute_l10n_tr_count_line_ids',
        store=True,
        readonly=False,
    )

    @api.depends('current_check_id.l10n_tr_response_line_ids')
    def _compute_l10n_tr_count_line_ids(self):
        for wizard in self:
            check = wizard.current_check_id
            commands = [Command.clear()]
            if check.test_type == 'unit_count':
                commands += [
                    Command.create({'response_line_id': line.id, **line._l10n_tr_get_counted_values()})
                    for line in check.l10n_tr_response_line_ids
                ]
            wizard.l10n_tr_count_line_ids = commands

    def _l10n_tr_apply_count(self):
        for line in self.l10n_tr_count_line_ids:
            line.response_line_id.write(line._l10n_tr_get_counted_values())

    def do_pass(self):
        # The check turns the counted quantities into the answer, so they have to reach it first.
        self._l10n_tr_apply_count()
        return super().do_pass()

    def do_fail(self):
        self._l10n_tr_apply_count()
        return super().do_fail()
