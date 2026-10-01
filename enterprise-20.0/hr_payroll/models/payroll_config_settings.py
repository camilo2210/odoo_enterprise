# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class PayrollConfigSettings(models.Model):
    _name = 'payroll.config.settings'
    _description = 'Payroll Configuration'
    _order = 'date_version'
    _rec_name = 'date_version'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        ondelete='cascade',
        default=lambda self: self.env.company,
    )
    parent_id = fields.Many2one(
        "payroll.config.settings",
        string="Parent Configuration",
        compute="_compute_parent_id",
        store=True,
        readonly=False,
    )
    date_version = fields.Date(
        string='Effective Date',
        required=True,
        default=fields.Date.context_today,
    )

    date_start = fields.Date(compute='_compute_dates', store=True)
    date_end = fields.Date(compute='_compute_dates', store=True)

    company_name = fields.Char(related='company_id.name')
    company_logo = fields.Binary(related='company_id.logo')
    country_code = fields.Char(related='company_id.country_code')

    _check_unique_date_version = models.UniqueIndex('(company_id, date_version)',
        'A company cannot have multiple versions sharing the same effective date.',
    )

    @api.depends('company_id.parent_id', 'date_version')
    def _compute_parent_id(self):
        for config in self:
            parent_configs = config.company_id.parent_id.payroll_config_ids
            config.parent_id = parent_configs.filtered(lambda c: c.date_version <= config.date_version).sorted(
                lambda c: c.date_version, reverse=True,
            )[:1]

    @api.depends('date_version', 'company_id', 'company_id.payroll_config_ids.date_version')
    def _compute_dates(self):
        for version in self:
            version.date_start = version.date_version

        all_versions = self.search_fetch([
            ('company_id', 'in', self.company_id.ids),
            ('date_version', '>', min(self.mapped('date_start'), default=date.today())),
        ], ['company_id', 'date_version'], order='date_version').grouped('company_id')
        for version in self:
            date_version_end = False
            if next_versions := all_versions.get(version.company_id):
                date_version_end = next((d for d in next_versions.mapped('date_version') if d > version.date_version), None)
                if date_version_end:
                    date_version_end -= relativedelta(days=1)
            version.date_end = date_version_end

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        default = default or {}
        for line, vals in zip(self, vals_list):
            vals['date_version'] = default.get('date_version', fields.Date.context_today(line).replace(day=1))
        return vals_list

    @api.ondelete(at_uninstall=True)
    def _unlink_except_last_version(self):
        configs_by_company = dict(self.env['payroll.config.settings']._read_group(
            domain=[('company_id', 'in', self.company_id.ids)],
            groupby=['company_id'],
            aggregates=['id:recordset'],
        ))
        for company in self.company_id:
            if not (configs_by_company.get(company) - self):
                raise UserError(self.env._(
                    "You cannot delete the only payroll configuration of %(company)s. "
                    "A company must always keep at least one configuration.",
                    company=company.display_name,
                ))

    def _get_fields_to_copy_from_parent(self):
        # to be overridden in l10n
        return [] + self._get_branch_editable_fields()

    def _get_branch_editable_fields(self):
        # to be overridden in l10n
        return []

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        branch_vals_list = res._get_branch_versions_from_parent_vals()
        if branch_vals_list:
            super().create(branch_vals_list)
        return res

    def write(self, vals):
        res = super().write(vals)
        self._push_changed_fields_to_child_configs(vals)
        return res

    def _convert_field_value_for_create(self, field_name, value):
        field = self._fields[field_name]
        if field.type == 'many2one':
            return value.id
        if field.type in ('one2many', 'many2many'):
            return [(6, 0, value.ids)]
        return value

    def _get_branch_versions_from_parent_vals(self):
        branch_vals_list = []
        editable_fields = self._get_branch_editable_fields()
        for parent_config in self.filtered(lambda config: config.company_id.child_ids):
            date_version = parent_config.date_version
            for branch in parent_config.company_id.child_ids:
                if branch.payroll_config_ids.filtered(lambda config: config.date_version == date_version):
                    continue
                vals = parent_config.copy_data(default={
                    'company_id': branch.id,
                    'parent_id': parent_config.id,
                    'date_version': date_version,
                })[0]

                branch_previous = branch.payroll_config_ids.filtered(
                    lambda config: config.date_version < date_version,
                ).sorted('date_version')[-1:]
                if branch_previous:
                    for field_name in editable_fields:
                        if branch_previous[field_name] != parent_config[field_name]:
                            vals[field_name] = self._convert_field_value_for_create(field_name, branch_previous[field_name])
                branch_vals_list.append(vals)
        return branch_vals_list

    def _push_changed_fields_to_child_configs(self, vals):
        fields_to_copy = self._get_fields_to_copy_from_parent()
        changed_shared_fields = [field for field in fields_to_copy if field in vals]
        if not changed_shared_fields:
            return
        children_by_parent = dict(self.env['payroll.config.settings']._read_group(
            domain=[('parent_id', 'in', self.ids)],
            groupby=['parent_id'],
            aggregates=['id:recordset'],
        ))
        if not children_by_parent:
            return
        for parent, children in children_by_parent.items():
            for child in children:
                for field in changed_shared_fields:
                    child[field] = parent[field] if not child[field] else child[field]
