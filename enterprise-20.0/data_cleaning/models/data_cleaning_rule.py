# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import models, api, fields
from odoo.tools import html2plaintext, SQL
from odoo.exceptions import ValidationError


ACTIONS_PYTHON = {
    'trim_all': lambda record, value: value.replace(' ', ''),
    'trim_superfluous': lambda record, value: re.sub(r'\s+', ' ', value.strip()),
    'case_first': lambda record, value: value.title(),
    'case_upper': lambda record, value: value.upper(),
    'case_lower': lambda record, value: value.lower(),
    'phone': lambda record, value: record._phone_format(number=value, country=record.country_id, force_format="INTERNATIONAL"),
    'html': lambda record, value: html2plaintext(value),
}

ACTIONS_SQL = {
    # {action_technical: (operator, action, composable))}
    'trim_all': (SQL('<>'), lambda val: SQL("REPLACE(%s, ' ', '')", val), True),
    'trim_superfluous': (SQL('<>'), lambda val: SQL(r"TRIM(REGEXP_REPLACE(%s, '\s+', ' ', 'g'))", val), True),
    'case_first': (SQL('<>'), lambda val: SQL('INITCAP(%s)', val), True),
    'case_upper': (SQL('<>'), lambda val: SQL('UPPER(%s)', val), True),
    'case_lower': (SQL('<>'), lambda val: SQL('LOWER(%s)', val), True),
    'html': (SQL('~'), lambda _val: SQL("'<[a-z]+.*>'"), False),
    # special cases (operator is False),
    # needs to be treated in Python with data_cleaning.model's method '_clean_records_%s' % action_technical
    'phone': (False, 'format_phone', False),
}


class Data_CleaningRule(models.Model):
    _name = 'data_cleaning.rule'
    _description = 'Cleaning Rule'
    _order = 'sequence'

    name = fields.Char(related='field_id.name')
    cleaning_model_id = fields.Many2one(
        'data_cleaning.model', string='Cleaning Model', required=True, index=True, ondelete='cascade')
    res_model_id = fields.Many2one(
        related='cleaning_model_id.res_model_id', readonly=True, store=True)
    res_model_name = fields.Char(
        related='cleaning_model_id.res_model_name', string='Model Name', readonly=True, store=True)
    field_id = fields.Many2one(
        'ir.model.fields', string='Field',
        domain="[('model_id', '=', res_model_id), ('ttype', 'in', ('char', 'text', 'html')), ('store', '=', True)]",
        required=True, ondelete='cascade')

    action = fields.Selection(
        [
            ('trim', 'Trim Spaces'),
            ('case', 'Set Type Case'),
            ('phone', 'Format Phone'),
            ('html', 'Scrap HTML'),
        ],
        string='Action', default='trim', required=True)
    action_trim = fields.Selection(
        [
            ('all', 'All Spaces'),
            ('superfluous', 'Superfluous Spaces'),
        ],
        string='Trim', default='all',
        help="Which spaces are trimmed by the rule. Leading, trailing, and successive spaces are considered superfluous.")
    action_case = fields.Selection(
        [
            ('first', 'First Letters to Uppercase'),
            ('upper', 'All Uppercase'),
            ('lower', 'All Lowercase'),
        ],
        string='Case', default='first',
        help="How the type case is set by the rule. 'First Letters to Uppercase' sets every letter to lowercase except the first letter of each word, which is set to uppercase.")
    action_technical = fields.Char(compute='_compute_action')
    action_display = fields.Char(compute='_compute_action')

    sequence = fields.Integer(string='Sequence', default=1)

    @api.depends('action', 'action_trim', 'action_case')
    def _compute_action(self):
        def get_display_name(rule, field_name):
            action = rule[field_name]
            selections = self._fields[field_name]._description_selection(self.env)
            return action, next((label for key, label in selections if key == action), '')
        for rule in self:
            action, action_display = get_display_name(rule, 'action')
            action_display = action_display or ''
            if action in ('trim', 'case'):
                action_detail, action_display_detail = get_display_name(rule, f'action_{action}')
                action = f"{action}_{action_detail}"
                action_display = f"{action_display} ({action_display_detail})"
            rule.action_technical = action
            rule.action_display = action_display

    def _action_to_sql(self):
        field_actions = {}
        for rule in self:
            operator, action, composable = ACTIONS_SQL.get(rule.action_technical)
            field_action = field_actions.setdefault(rule.name, {
                'action': (lambda v: v) if composable else action,
                'rule_ids': [],
                'field_name': rule.name,
                'field_id': rule.field_id.id,
                'operator': operator,
            })
            field_action['rule_ids'].extend(rule.ids)
            if composable:
                field_action['action'] = lambda v, *, a=action, b=field_action['action']: a(b(v))
        return field_actions

    def _action_to_python(self):
        self.ensure_one()
        return ACTIONS_PYTHON.get(self.action_technical)

    @api.onchange('action')
    def _onchange_action(self):
        if self.action == 'phone':
            try:
                import phonenumbers
            except ModuleNotFoundError:
                raise ValidationError(self.env._('The Python module `phonenumbers` is not installed. Format phone will not work.'))
