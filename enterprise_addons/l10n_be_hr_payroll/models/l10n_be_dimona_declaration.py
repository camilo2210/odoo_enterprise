# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import UserError

DECLARATION_TYPES = {
    'dimonaIn': 'dimona_in',
    'dimonaOut': 'dimona_out',
    'dimonaUpdate': 'dimona_update',
    'dimonaCancel': 'dimona_cancel',
}


class L10nBeDimonaDeclaration(models.Model):
    _name = 'l10n.be.dimona.declaration'
    _description = 'Dimona Declaration'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(fields)

    name = fields.Char('Declaration ID', readonly=True, index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    content = fields.Json(help="The declaration as the ONSS answered it.")
    request_content = fields.Json(help="The declaration as it was filed.")
    declaration_type = fields.Selection([
        ('dimona_in', 'Dimona In'),
        ('dimona_out', 'Dimona Out'),
        ('dimona_update', 'Dimona Update'),
        ('dimona_cancel', 'Dimona Cancel'),
    ], compute='_compute_declaration_info', store=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', compute='_compute_declaration_info', store=True, readonly=True, index=True)
    version_id = fields.Many2one('hr.version')
    period_id = fields.Many2one('l10n.be.dimona.period', compute='_compute_declaration_info', store=True, readonly=True, index='btree_not_null')
    date_start = fields.Date(compute='_compute_declaration_info', store=True, readonly=True)
    date_end = fields.Date(compute='_compute_declaration_info', store=True, readonly=True)
    state = fields.Selection([
        ('A', 'Accepted'),
        ('W', 'Accepted with Warnings'),
        ('B', 'Refused'),
        ('S', 'Waiting Sigedis'),
    ], compute='_compute_declaration_info', store=True, readonly=True)
    employee_birth_date = fields.Date(compute='_compute_declaration_info', store=True, readonly=True)
    employee_name = fields.Char(compute='_compute_declaration_info', store=True, readonly=True)

    _constraint_name_unique = models.Constraint(
        definition='unique(name)',
        message="The dimona declaration ID must be unique!",
    )

    def _l10n_be_dimona_period_id(self):
        """The ONSS period this declaration opened, as every follow-up must quote it."""
        self.ensure_one()
        if not self.name:
            raise UserError(_(
                "The DIMONA entrance declaration of %s has not been answered by the ONSS "
                "yet, so the period it opens is not known. No further declaration can be "
                "filed against it until it is.", self.employee_name or self.employee_id.name))
        return int(self.name)

    def _dimona_apply_response(self, content, reference=False):
        """Apply an answer the ONSS gave for this declaration.

        Idempotent: _compute_declaration_info only posts to the chatter and moves the
        version's next action when the stored status actually changes, so replaying an
        answer -- as any at-least-once inbound channel eventually will -- changes nothing.
        """
        self.ensure_one()
        vals = {}
        if reference and not self.name:
            vals['name'] = str(reference)
        if content and content != self.content:
            vals['content'] = content
        if vals:
            self.write(vals)
        self._dimona_response_applied(vals)
        return bool(vals)

    def _dimona_response_applied(self, vals):
        """Hook for the work that only becomes possible once an answer is in."""

    @api.depends('content', 'request_content', 'employee_id.name', 'employee_id.birthday', 'company_id')
    def _compute_declaration_info(self):
        for declaration in self:
            content = declaration.content
            birth_date = False
            full_name = False
            if declaration.employee_id:
                birth_date = declaration.employee_id.birthday
                full_name = declaration.employee_id.name
            # The type is what was filed; the answer merely repeats it back.
            declaration.declaration_type = next(
                (declaration_type
                 for key, declaration_type in DECLARATION_TYPES.items()
                 if key in (content or declaration.request_content or {})),
                False)
            if not content:
                declaration.period_id = False
                declaration.date_start = False
                declaration.date_end = False
                declaration.state = False
                declaration.employee_birth_date = birth_date
                declaration.employee_name = full_name
                continue
            if 'worker' in content and not declaration.employee_id:
                declaration.employee_id = self.env['hr.employee'].with_context(active_test=False).search([
                    ('niss', '=', content['worker']['ssin']),
                    ('company_id', '=', declaration.company_id.id),
                ], order="active DESC", limit=1)
                if declaration.employee_id:
                    birth_date = declaration.employee_id.birthday
                    full_name = declaration.employee_id.name
                else:
                    if 'birthDate' in content['worker']:
                        birth_date = fields.Date.from_string(content['worker']['birthDate'])
                    full_name = ' '.join([content['worker'].get('givenName', ''), content['worker'].get('familyName', '')]).strip()

            declaration.employee_birth_date = birth_date
            declaration.employee_name = full_name

            post_message = False
            if 'declarationStatus' in content and 'result' in content['declarationStatus']:
                new_state = content['declarationStatus']['result']
                if declaration.state != new_state:
                    post_message = True
                declaration.state = new_state
            if 'declarationStatus' in content and 'period' in content['declarationStatus']:
                declaration.period_id = self.env['l10n.be.dimona.period'].search([
                    ('name', '=', content['declarationStatus']['period']['id']),
                    ('company_id', '=', declaration.company_id.id)])
            date_start = False
            date_end = False
            for key in DECLARATION_TYPES:
                if key in content:
                    date_start = content[key].get('startDate', False)
                    date_end = content[key].get('endDate', False)
                    break

            if date_start:
                (year, month, day) = date_start.split('-')
                declaration.date_start = date(int(year), int(month), int(day))

            if date_end:
                (year, month, day) = date_end.split('-')
                declaration.date_end = date(int(year), int(month), int(day))

            if post_message and declaration.employee_id:
                if declaration.state == 'A':
                    declaration.employee_id.version_id.l10n_be_dimona_next_action = 'done'
                    declaration.employee_id.message_post(body=_('DIMONA declaration treated and accepted without anomalies'))
                elif declaration.state == 'W':
                    declaration.employee_id.version_id.l10n_be_dimona_next_action = 'done'
                    declaration.employee_id.message_post(body=_(
                        'DIMONA declaration treated and accepted with non blocking anomalies\n%(anomalies)s\n%(informations)s',
                        anomalies=content.get('declarationStatus', {}).get('anomalies', _('Unknown')),
                        informations=content.get('declarationStatus', {}).get('informationsCollection', _('Unknown'))))
                elif declaration.state == 'B':
                    declaration.employee_id.version_id.l10n_be_dimona_next_action = 'issue'
                    declaration.employee_id.message_post(body=_(
                        'DIMONA declaration treated and refused (blocking anomalies)\n%s',
                        content.get('declarationStatus', {}).get('anomalies', _('Unknown'))))
                elif declaration.state == 'S':
                    declaration.employee_id.version_id.l10n_be_dimona_next_action = 'progress'
                    declaration.employee_id.message_post(body=_('DIMONA declaration waiting worker identification by Sigedis'))

            if declaration.declaration_type == 'dimona_in' and declaration.employee_id:
                start = declaration.date_start
                end = declaration.date_end or fields.Date.today()
                versions_by_employee = declaration.employee_id._get_contract_versions(
                    date_start=start,
                    date_end=end,
                    domain=Domain('l10n_be_dimona_declaration_id', '=', False))
                for _date, versions in versions_by_employee[declaration.employee_id.id].items():
                    versions.l10n_be_dimona_declaration_id = declaration
                    if not declaration.version_id:
                        declaration.version_id = versions[0]
