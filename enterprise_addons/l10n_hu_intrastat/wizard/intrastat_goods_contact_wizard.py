from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class L10nHUIntrastatGoodsContactWizard(models.TransientModel):
    _name = 'l10n_hu_intrastat.intrastat.goods.contact.wizard'
    _description = "Intrastat Goods Contact Wizard"

    def _domain_contact(self):
        return Domain.OR([
            Domain('parent_id', 'child_of', self.env.company.partner_id.id),
            Domain('parent_id', 'parent_of', self.env.company.partner_id.id),
            Domain('id', '=', self.env.user.partner_id.id),
        ])

    @api.model
    def default_get(self, fields):
        results = super().default_get(fields)
        if 'l10n_hu_intrastat_contact_executive' in fields and 'l10n_hu_intrastat_contact_executive' not in results:
            results['l10n_hu_intrastat_contact_executive'] = self.env.company.l10n_hu_intrastat_contact_executive.id
        if 'l10n_hu_intrastat_contact_executive_status' in fields and 'l10n_hu_intrastat_contact_executive_status' not in results:
            results['l10n_hu_intrastat_contact_executive_status'] = self.env.company.l10n_hu_intrastat_contact_executive_status
        if 'l10n_hu_intrastat_contact_person' in fields and 'l10n_hu_intrastat_contact_person' not in results:
            results['l10n_hu_intrastat_contact_person'] = self.env.user.partner_id.id
        return results

    company_id = fields.Many2one(comodel_name='res.company', required=True)
    return_id = fields.Many2one(comodel_name='account.return', required=True)

    l10n_hu_intrastat_contact_executive = fields.Many2one(
        comodel_name='res.partner',
        string="Executive",
        help='Manager approving the questionnaire. This information can be stored in the company form under "Intrastat Executive".',
        domain=lambda self: self._domain_contact(),
        readonly=False,
    )
    l10n_hu_intrastat_contact_executive_status = fields.Char(
        string="Executive Position",
        help='Job position of the manager approving the questionnaire. This information can be stored in the company form under "Intrastat Executive Position".',
        readonly=False,
    )
    l10n_hu_intrastat_contact_person = fields.Many2one(
        comodel_name='res.partner',
        string="Contact Person",
        help="The person completing the questionnaire.",
        domain=lambda self: self._domain_contact(),
        readonly=False,
    )
    l10n_hu_intrastat_contacts_validity = fields.Boolean(compute='_compute_l10n_hu_intrastat_contacts_validity')

    @api.model
    def _get_contacts_validity_dependencies(self):
        dependencies = ['l10n_hu_intrastat_contact_executive', 'l10n_hu_intrastat_contact_person']
        return dependencies + [f'{contact}.{field}' for contact in dependencies for field in self._get_mandatory_contact_fields()]

    @api.depends(lambda self: self._get_contacts_validity_dependencies())
    def _compute_l10n_hu_intrastat_contacts_validity(self):
        for wizard in self:
            wizard.l10n_hu_intrastat_contacts_validity = wizard._check_contacts_validity()

    def _check_contacts_validity(self):
        self.ensure_one()
        for contact in (self.l10n_hu_intrastat_contact_executive, self.l10n_hu_intrastat_contact_person):
            if not contact or not all(contact[field] for field in self._get_mandatory_contact_fields()):
                return False
        return True

    def _get_mandatory_contact_fields(self):
        return ('name', 'phone', 'email')

    def action_submit_contacts(self):
        if not self._check_contacts_validity():
            raise ValidationError(self.env._("The executive and/or contact person is missing either a name, an email, or a phone number."))
        # Write the executive contact on company if user has the rights to do so
        if self.company_id.has_access('write'):
            self.company_id.write({
                contact_field: self[contact_field].id if isinstance(self[contact_field], self.env['res.partner'].__class__) else self[contact_field]
                for contact_field in ('l10n_hu_intrastat_contact_executive', 'l10n_hu_intrastat_contact_executive_status')
                if self[contact_field] != self.company_id[contact_field]
            })
        return self.env['l10n_hu_intrastat.intrastat.goods.submission.wizard']._l10n_hu_intrastat_open_submission_wizard(
            self.return_id,
            contact_executive=self.l10n_hu_intrastat_contact_executive,
            contact_executive_status=self.l10n_hu_intrastat_contact_executive_status,
            contact_person=self.l10n_hu_intrastat_contact_person,
        )
