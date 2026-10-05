from odoo import api, fields, models
from odoo.fields import Domain


class EsgEmissionSource(models.Model):
    _name = 'esg.emission.source'
    _description = 'Emission Source'
    _order = 'level desc,sequence,name'
    _rec_name = 'complete_name'
    _parent_name = 'parent_id'
    _parent_store = True

    sequence = fields.Integer(default=10)
    name = fields.Char(translate=True, required=True)
    parent_id = fields.Many2one('esg.emission.source', domain="['!', ('id', 'child_of', id)]", index=True)
    child_ids = fields.One2many('esg.emission.source', 'parent_id')
    parent_path = fields.Char(index=True)
    complete_name = fields.Char(compute='_compute_complete_name', search='_search_complete_name', recursive=True)
    scope = fields.Selection(selection=[
            ('direct', 'Scope 1: Direct'),
            ('indirect', 'Scope 2: Indirect'),
            ('indirect_others', 'Scope 3: Others Indirect')
        ],
        default='direct',
        compute='_compute_scope',
        store=True,
        readonly=False,
        recursive=True,
        required=True,
        help="Shows whether emissions are direct, from energy use, or indirect from the value chain.",
    )
    emission_factor_ids = fields.One2many('esg.emission.factor', 'source_id')

    activity_flow_direct_indirect = fields.Selection(
        selection=[
            ('company_reporting', 'Company Reporting'),
            ('upstream', 'Upstream'),
        ],
        compute='_compute_activity_flow',
        export_string_translation=False,
    )
    activity_flow_indirect_others = fields.Selection(
        selection=[
            ('upstream', 'Upstream'),
            ('downstream', 'Downstream'),
        ],
        required=True,
        default='upstream',
        export_string_translation=False,
    )
    activity_flow = fields.Selection(
        selection=lambda self: list(set(self._fields['activity_flow_direct_indirect'].selection) | set(self._fields['activity_flow_indirect_others'].selection)),
        compute='_compute_activity_flow',
    )

    level = fields.Integer(compute='_compute_level', store=True, recursive=True)

    @api.depends('parent_id.level')
    def _compute_level(self):
        for source in self:
            if not source.parent_id:
                source.level = 1
            else:
                source.level = source.parent_id.level + 1

    @api.depends('parent_id.scope')
    def _compute_scope(self):
        for source in self:
            if not source.parent_id:
                continue
            source.scope = source.parent_id.scope

    @api.depends('scope', 'activity_flow_indirect_others')
    def _compute_activity_flow(self):
        for source in self:
            source.activity_flow_direct_indirect = source.activity_flow = False
            match source.scope:
                case 'direct':
                    source.activity_flow_direct_indirect = source.activity_flow = 'company_reporting'
                case 'indirect':
                    source.activity_flow_direct_indirect = source.activity_flow = 'upstream'
                case 'indirect_others':
                    source.activity_flow = source.activity_flow_indirect_others

    @api.depends('name', 'parent_id.complete_name', 'scope')
    def _compute_complete_name(self):
        for source in self:
            if source.parent_id:
                prefix = source.parent_id.complete_name
            else:
                prefix = dict(self.env['esg.emission.source']._fields['scope']._description_selection(self.env)).get(source.scope)
            source.complete_name = f"{prefix} > {source.name}" if source.name else prefix

    @api.model
    def _search_complete_name(self, operator, value):
        if operator not in ('ilike', 'like', '=', '=ilike'):
            raise NotImplementedError(f"Operator {operator} not supported")

        domain = Domain('name', operator, value)

        scope_labels = dict(self.env['esg.emission.source']._fields['scope']._description_selection(self.env))
        matching_scope_keys = [
            key for key, label in scope_labels.items()
            if (
                operator in ('ilike', '=ilike') and value in label.lower()
            ) or (
                operator in ('like', '=') and value in label
            )
        ]
        if matching_scope_keys:
            domain |= Domain('scope', 'in', matching_scope_keys)
        matched_sources = self.env['esg.emission.source'].search(domain)

        if not matched_sources:
            return Domain.FALSE
        return Domain('id', 'child_of', matched_sources.ids)
