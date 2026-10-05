from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountSplitJournalItemWizard(models.TransientModel):
    _name = 'account.split.journal.item.wizard'
    _description = "Wizard that splits journal items into multiple journal items"

    line_ids = fields.Many2many('account.move.line', 'account_split_journal_item_move_line_rel', 'wizard_id', 'line_id')
    line_currency_id = fields.Many2one(comodel_name='res.currency')
    quantity = fields.Integer(string="Quantity")
    amount = fields.Monetary(string="Amount", currency_field='line_currency_id')
    account_id = fields.Many2one(comodel_name='account.account', string="Account")

    show_simple_wizard = fields.Boolean(compute='_compute_show_simple_wizard')

    @api.depends('quantity', 'line_ids')
    def _compute_show_simple_wizard(self):
        for wizard in self:
            wizard.show_simple_wizard = wizard.quantity != 2 or len(wizard.line_ids) > 1

    @api.onchange('quantity')
    def _onchange_quantity(self):
        for wizard in self:
            if len(wizard.line_ids) == 1 and wizard.quantity:
                wizard.amount = abs(wizard.line_ids.balance) / wizard.quantity

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        self = self.browse()  # noqa: PLW0642

        if defaults.get('line_ids'):
            line_ids = self._fields['line_ids'].convert_to_cache(defaults.get('line_ids'), self)

            if lines := self.env['account.move.line'].browse(line_ids):
                if not all(move.state == 'draft' for move in lines.move_id):
                    raise UserError(_("Selected lines should only be part of moves in draft."))

                if len(lines) == 1:
                    defaults['quantity'] = int(lines.quantity) if lines.quantity > 1 else 2
                    defaults['line_currency_id'] = lines.currency_id.id
                    defaults['amount'] = abs(lines.balance) / defaults['quantity']
                    defaults['account_id'] = lines.account_id.id
                else:
                    defaults['quantity'] = 2

        return defaults

    def split(self):
        self.ensure_one()

        if self.quantity <= 1:
            raise UserError(_("Quantity must be greater than 1."))

        if len(self.line_ids) == 1 and self.quantity == 2:
            original_balance = abs(self.line_ids.balance)
            if not (0 < self.amount < original_balance):
                raise UserError(_("The split amount must be strictly between 0 and the original line amount."))

        container = {'records': self.line_ids.move_id}
        with (
            self.env['account.move']._check_balanced(container),
            self.env['account.move']._sync_dynamic_lines(container),
        ):
            new_lines_vals = []
            for line in self.line_ids:
                fname = (
                    'balance' if line.move_id.move_type == 'entry' else
                    'price_unit' if not self.show_simple_wizard else
                    'quantity'
                )
                convert_to_cache = line._fields[fname].convert_to_cache  # round according to the field

                if not self.show_simple_wizard:
                    split_amount = convert_to_cache(line[fname] * self.amount / abs(line.balance), line)
                    orig_amount = convert_to_cache(line[fname] - split_amount, line)
                    vals_list = [
                        {fname: orig_amount, 'account_id': line.account_id.id},
                        {fname: split_amount, 'account_id': self.account_id.id},
                    ]
                else:
                    running_amount = line[fname]
                    vals_list = []
                    for i in range(self.quantity):
                        running_amount -= (current_amount := convert_to_cache(running_amount / (self.quantity - i), line))
                        vals_list.append({fname: current_amount, 'account_id': line.account_id.id})

                line.write(vals_list[0])
                for vals in vals_list[1:]:
                    new_lines_vals.append(line.copy_data(vals | {
                        fname: val
                        for fname in ('deferred_start_date', 'deferred_end_date')
                        if (val := line[fname])
                    })[0])

            self.env['account.move.line'].create(new_lines_vals)
