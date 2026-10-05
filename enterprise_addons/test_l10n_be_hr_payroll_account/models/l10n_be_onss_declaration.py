# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class L10nBeOnssDeclaration(models.Model):
    _inherit = 'l10n.be.onss.declaration'

    batch_declaration_name = fields.Char(compute='_compute_batch_declaration_name')

    def _compute_batch_declaration_name(self):
        for record in self:
            record.batch_declaration_name = record.batch_declaration_id._name if record.batch_declaration_id else False

    def action_post(self):
        """ Sandbox mode: Test Declarations (S) are never uploaded to the ONSS
        SFTP server, so no credentials are required. The posting is only
        simulated, allowing to test the complete batch DmfA flow together with
        the answer wizard (test.l10n.be.dmfa.sandbox.answer).
        """
        sandbox_declarations = self.filtered(lambda d: d.environment == 'S')
        other_declarations = self - sandbox_declarations

        errors = []
        for batch_declaration in sandbox_declarations.mapped('batch_declaration_id'):
            if declaration_errors := batch_declaration._pre_submit_checks():
                errors.append(self.env._("Declaration %(name)s: %(errors)s", name=batch_declaration.name, errors='\n\t- '.join(declaration_errors)))

        for declaration in sandbox_declarations:
            declaration.state = 'posted'
            declaration.batch_declaration_id.message_post(body=self.env._(
                'The %(declaration)s (id=%(declaration_id)s) has been posted by %(user)s in sandbox mode, '
                'no file has been sent to the ONSS servers',
                declaration=declaration._get_html_link(self.env._('declaration')),
                declaration_id=declaration.id,
                user=self.env.user.name))

        next_action = {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }
        if other_declarations:
            next_action = super(L10nBeOnssDeclaration, other_declarations).action_post()

        if sandbox_declarations:
            next_action = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': self.env._("Test Declarations posted in sandbox mode (no file sent to the ONSS)"),
                    'next': next_action,
                },
            }

        if errors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'title': self.env._("The following errors were found when posting sandbox declarations"),
                    'message': '\n'.join(errors),
                    'sticky': True,
                    'next': next_action,
                },
            }
        return next_action

    def action_open_dmfa_sandbox_answer_wizard(self):
        self.ensure_one()
        return {
            'name': self.env._('Simulate ONSS Answer'),
            'type': 'ir.actions.act_window',
            'res_model': 'test.l10n.be.dmfa.sandbox.answer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_onss_declaration_id': self.id},
        }
