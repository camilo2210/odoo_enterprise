from markupsafe import Markup
from odoo import Command, _, api, fields, models


class SodaImportWizard(models.TransientModel):
    _name = 'soda.import.wizard'
    _description = 'Import a SODA file and map accounts and analytics'

    # A dict mapping the SODA reference to a dict with a list of `entries` and an `attachment_id`
    # {
    #     'soda_reference_1': {
    #         'entries': [
    #             {
    #                 'code': '1200',
    #                 'name': 'Line Description',
    #                 'debit': '150.0',
    #                 'credit': '0.0',
    #                 'department': 'DEP',
    #             },
    #             ...
    #         ],
    #         'attachment_id': 'attachment_id_1',
    #     },
    #     ...
    # }

    company_id = fields.Many2one(comodel_name='res.company', required=True)
    journal_id = fields.Many2one(comodel_name='account.journal')
    soda_files = fields.Json()
    # A dict mapping the SODA account code to its description
    soda_code_to_name_mapping = fields.Json(required=False)
    soda_account_mapping_ids = fields.Many2many(comodel_name='soda.account.mapping', compute='_compute_soda_account_mapping_ids', readonly=False)

    soda_departments = fields.Json(required=False)
    soda_analytic_mapping_ids = fields.Many2many(comodel_name='soda.analytic.mapping', compute='_compute_soda_analytic_mapping_ids', readonly=False)
    soda_show_analytic = fields.Boolean(compute='_compute_soda_show_analytic')

    @api.depends('soda_code_to_name_mapping', 'company_id')
    def _compute_soda_account_mapping_ids(self):
        for wizard in self:
            soda_account_mappings = self.env['soda.account.mapping'].find_or_create_account_mappings(
                wizard.soda_code_to_name_mapping,
                wizard.company_id
            )
            wizard.soda_account_mapping_ids = soda_account_mappings.ids

    @api.depends('company_id')
    def _compute_soda_analytic_mapping_ids(self):
        for wizard in self:
            soda_analytic_mapping_ids = self.env['soda.analytic.mapping'].find_or_create_analytic_mappings(
                wizard.soda_departments,
                wizard.company_id,
            )
            wizard.soda_analytic_mapping_ids = soda_analytic_mapping_ids

    @api.depends('company_id')
    def _compute_soda_show_analytic(self):
        for wizard in self:
            company = wizard.company_id
            wizard.soda_show_analytic = company.l10n_be_soda_use_analytic and company.l10n_be_soda_analytic_plan

    def _action_save_and_import(self, existing_move=None):
        # We find all mapping lines where there's no account set
        soda_account_mapping = {}
        for account_mapping in self.soda_account_mapping_ids:
            soda_account_mapping[account_mapping.code] = {
                'account_id': account_mapping.account_id.id,
                'name': account_mapping.name,
            }
        soda_analytic_mapping = {}
        # sudo: only the 'Analytic Accounting' group can access the analytic account, even if analytic accounting is entirely disabled
        for analytic_mapping in self.soda_analytic_mapping_ids.sudo():
            soda_analytic_mapping[analytic_mapping.department] = analytic_mapping.analytic_account_id.id

        if self.env.context.get('soda_mapping_save_only', False):
            return False

        suspense_account = self.journal_id.company_id.account_journal_suspense_account_id
        non_mapped_soda_accounts = set()
        moves = self.env['account.move']
        for ref, soda_file in self.soda_files.items():
            line_ids = []
            # Every SODA file is linked to a move containing the entries according to the mapping
            for entry in soda_file['entries']:
                account_id = soda_account_mapping[entry['code']]['account_id']
                if not account_id:
                    account_id = suspense_account.id
                    non_mapped_soda_accounts.add((entry['code'], entry['name']))
                vals = {
                    'name': entry['name'] or soda_account_mapping[entry['code']]['name'],
                    'account_id': account_id,
                    'debit': entry['debit'],
                    'credit': entry['credit'],
                }
                if (department := entry.get('department')) and (account_id := soda_analytic_mapping.get(department)):
                    vals['analytic_distribution'] = {account_id: 100}
                line_ids.append(Command.create(vals))
            if not existing_move:
                move_vals = {
                    'move_type': 'entry',
                    'journal_id': self.journal_id.id,
                }
                move = self.env['account.move'].create(move_vals)
                attachment = self.env['ir.attachment'].browse(soda_file['attachment_id'])
                move.message_post(attachment_ids=attachment.ids)
                attachment.write({'res_model': 'account.move', 'res_id': move.id})
            else:
                move = existing_move
                # Avoid updating the same move multiple times. Should not happen as existing_move is set when
                # importing from email alias where _action_save_and_import method is called once per soda file.
                existing_move = None

            # 'tracking_disable' seems wanted, see odoo/enterprise#61015
            move.with_context(tracking_disable=True).write({
                'ref': ref,
                'date': soda_file['date'],
                'line_ids': line_ids,
            })
            if non_mapped_soda_accounts:
                move.message_post(
                    body=Markup("{first}<ul>{accounts}</ul>{second}<br/>{link}").format(
                        first=_("The following accounts were found in the SODA file but have no mapping:"),
                        accounts=Markup().join(Markup("<li>%s (%s)</li>") % (code, name) for code, name in non_mapped_soda_accounts),
                        second=_("They have been imported in the Suspense Account (499000) for now."),
                        link=_(
                            "For future imports, you can map them correctly in %(left)sConfiguration > Settings > Accounting > SODA%(right)s",
                            left=Markup("<a href='#action=account.action_account_config&model=res.config.settings'>"),
                            right=Markup("</a>"),
                        ),
                    )
                )
            if errors := self.env.context.get('errors', False):
                for error in errors:
                    move.message_post(body=error)
            moves += move
        return moves

    def action_save_and_import(self):
        moves = self._action_save_and_import()
        if not moves:       # When modifying (from the Settings) the mapping without importing a file,
            return False    # we don't want to redirect to the form/list view
        action_vals = {
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'context': self.env.context,
        }
        if not moves:
            return False
        if len(moves) == 1:
            action_vals.update({
                'domain': [('id', 'in', moves[0].ids)],
                'views': [[False, "form"]],
                'view_mode': 'form',
                'res_id': moves[0].id,
            })
        else:
            action_vals.update({
                'domain': [('id', 'in', moves.ids)],
                'views': [[False, "list"], [False, "kanban"], [False, "form"]],
                'view_mode': 'list, kanban, form',
            })
        # Redirect to the newly created move(s)
        return action_vals
