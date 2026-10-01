from odoo import fields, models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _domain_contact(self):
        return Domain('parent_id', '=', self.env.company.partner_id.id)

    l10n_hu_intrastat_contact_executive = fields.Many2one(
        comodel_name='res.partner',
        string="Intrastat Executive",
        domain=lambda self: self._domain_contact(),
        help="The executive approving Intrastat file submissions",
    )
    l10n_hu_intrastat_contact_executive_status = fields.Char(
        string="Intrastat Executive Position",
        help="Job position of the executive approving Intrastat file submissions"
    )
