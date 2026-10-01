# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models, SUPERUSER_ID
from odoo.fields import Domain
from odoo.tools.safe_eval import expr_eval
from odoo.tools.misc import format_date
from odoo.exceptions import UserError


class HrRuleParameterValue(models.Model):
    _name = 'hr.rule.parameter.value'
    _description = 'Salary Rule Parameter Value'
    _inherit = ['mail.track.mixin']
    _order = 'date_from desc'

    rule_parameter_id = fields.Many2one('hr.rule.parameter', required=True, index=True, ondelete='cascade', default=lambda self: self.env.context.get('active_id'))
    rule_parameter_name = fields.Char(related="rule_parameter_id.name", readonly=True)
    code = fields.Char(related="rule_parameter_id.code", index=True, store=True, readonly=True)
    date_from = fields.Date(string="From", index=True, required=True, tracking=1)
    parameter_value = fields.Text(help="Python data structure", required=True, tracking=2)
    country_id = fields.Many2one(related="rule_parameter_id.country_id")
    modified_by_user = fields.Boolean(readonly=True, copy=False)

    _unique_parameter = models.Constraint(
        'unique (rule_parameter_id, date_from)',
        "Two rules with the same code cannot start the same day",
    )

    @api.constrains('parameter_value')
    def _check_parameter_value(self):
        for value in self:
            try:
                expr_eval(value.parameter_value)
            except Exception as e:  # noqa: BLE001
                raise UserError(self.env._('Wrong rule parameter value for %(rule_parameter_name)s at date %(date)s.\n%(error)s', rule_parameter_name=value.rule_parameter_name, date=format_date(self.env, value.date_from), error=str(e)))

    @api.model_create_multi
    def create(self, vals_list):
        existing_values_domain = Domain.OR([[
            ('rule_parameter_id', '=', vals['rule_parameter_id']),
            ('date_from', '=', vals['date_from'])
        ] for vals in vals_list])
        existing_values = self.search(existing_values_domain)
        if existing_values:
            existing_values.unlink()
        self.env.transaction.invalidate_ormcache()
        for vals in vals_list:
            vals['modified_by_user'] = self.env.uid != SUPERUSER_ID
        parameter_values = super().create(vals_list)
        if self.env.uid != SUPERUSER_ID:
            empty_value = self.browse()  # all falsy fields
            tracked_fnames = {'parameter_value'}  # date_from embed in body, no need to track again
            for value in parameter_values:
                value.rule_parameter_id._track_record(
                    value,
                    tracked_fnames,
                    initial_values={value.id: {fname: empty_value[fname] for fname in tracked_fnames}},
                    body=Markup("<span class='fw-bold'>{date_label}</span>").format(
                        date_label=self.env._("Creating value for %s.", format_date(self.env, value.date_from)),
                    ),
                )
        return parameter_values

    def write(self, vals):
        tracked_fnames = self._track_get_fields() & set(vals.keys())
        if tracked_fnames:
            for value in self:
                value.rule_parameter_id._track_record(
                    value,
                    tracked_fnames,
                    body=Markup("<span class='fw-bold'>{date_label}</span>").format(
                        date_label=self.env._("Modifying value for %s.", format_date(self.env, value.date_from)),
                    ),
                )
            self.env.transaction.invalidate_ormcache()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def unlink_rule_parameter_value(self):
        if self.env.uid != SUPERUSER_ID:
            empty_value = self.browse()  # all falsy fields
            if SUPERUSER_ID in self.create_uid.mapped('id'):
                raise UserError(self.env._(
                    'You cannot delete a rule parameter value created by the system.\n'
                    'You can modify its value instead or archive the rule parameter.'))
            for value in self:
                value.rule_parameter_id._track_record(
                    value,
                    track_fnames=['parameter_value'],
                    end_values={value.id: {'parameter_value': empty_value['parameter_value']}},
                    body=Markup("<span class='fw-bold'>{date_label}</span>").format(
                        date_label=self.env._("Deleting value for %s.", format_date(self.env, value.date_from))
                    ),
                )
                # fire now: one track / line, and avoid spurious issues with unlink
                value._track_finalize()
