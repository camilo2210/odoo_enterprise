from odoo import fields, models
from odoo.fields import Domain


class SodaAnalyticMapping(models.Model):
    _name = 'soda.analytic.mapping'
    _description = 'SODA Analytic Mapping'
    _order = 'department, company_id'
    _check_company_auto = True

    company_id = fields.Many2one(comodel_name='res.company', required=True, default=lambda self: self.env.company)
    department = fields.Char(string='SODA Department', required=True)
    analytic_plan_id = fields.Many2one(related='company_id.l10n_be_soda_analytic_plan')
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Mapped Analytic Account',
        groups='analytic.group_analytic_accounting',
        domain="[('plan_id', '=', analytic_plan_id)]",
    )

    _department_company_uniq = models.Constraint(
        'unique (department, company_id)',
        "The department of the SODA analytic account must be unique per company",
    )

    def find_or_create_analytic_mappings(self, soda_departments, company_id):
        """Find analytic mappings for the provided SODA departments and/or create new ones when mappings for some SODA departments
        do not exist yet.

        :param soda_departments: a list of SODA departments
        :param company_id: the company for which to find or create the entries
        :return: a recordset of soda.analytic.mapping entries for the given SODA departments
        """
        soda_departments = soda_departments or []
        # Find existing analytic mappings for the provided SODA departments
        domain = self._check_company_domain(company_id)
        if soda_departments:
            domain &= Domain('department', 'in', soda_departments)

        soda_analytic_mappings = self.env['soda.analytic.mapping'].search(domain)
        soda_analytic_departments = set(soda_analytic_mappings.mapped('department'))
        new_soda_analytic_mappings = []

        for department in soda_departments:
            # For each SODA department where there's no mapping yet, we create a new (empty) one.
            if department not in soda_analytic_departments:
                soda_analytic_departments.add(department)
                new_soda_analytic_mappings.append({
                    'department': department,
                    'company_id': company_id.id,
                })

        soda_analytic_mappings |= self.env['soda.analytic.mapping'].create(new_soda_analytic_mappings)

        return soda_analytic_mappings

    def action_unlink(self):
        self.unlink()
        return self.env['res.config.settings'].l10n_be_soda_open_soda_mapping()
