# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import ast
import timeit
import logging
import re

import psycopg2.errors
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, modules
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL

DR_CREATE_STEP_AUTO = 1000
_logger = logging.getLogger(__name__)

# Merge list of list based on their common element
#   Input: [['a', 'b'], ['b', 'c'], ['d', 'e']]
#   Output: [['a', 'b', 'c'], ['d', 'e']]
# https://stackoverflow.com/a/9112588
def merge_common_lists(lsts):
    sets = [set(lst) for lst in lsts if lst]
    merged = True
    while merged:
        merged = False
        results = []
        while sets:
            common, rest = sets[0], sets[1:]
            sets = []
            for x in rest:
                if x.isdisjoint(common):
                    sets.append(x)
                else:
                    merged = True
                    common |= x
            results.append(common)
        sets = results
    return sets


class Data_MergeModel(models.Model):
    _name = 'data_merge.model'
    _description = 'Deduplication Model'
    _order = 'name'

    name = fields.Char(string='Name', readonly=False, store=True, required=True, copy=False, compute='_compute_name')
    active = fields.Boolean(default=True)

    res_model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    res_model_name = fields.Char(related='res_model_id.model', string='Model Name', readonly=True, store=True)
    domain = fields.Char(string='Domain', help='Records eligible for the deduplication process')
    removal_mode = fields.Selection([
        ('archive', 'Archive'),
        ('delete', 'Delete')], string='Duplicate Removal', default='archive')
    merge_mode = fields.Selection([
        ('manual', 'Manual'),
        ('automatic', 'Automatic')], string='Merge Mode', default='manual')
    custom_merge_method = fields.Boolean(compute='_compute_custom_merge_method')

    rule_ids = fields.One2many('data_merge.rule', 'model_id', string="Deduplication Rules", help='Suggest to merge records matching at least one of these rules')
    records_to_merge_count = fields.Integer(compute='_compute_records_to_merge_count')

    mix_by_company = fields.Boolean('Cross-Company', default=False, help="In Manual Mode, the system identifies duplicates across your selected companies for review. "
                                                                         "In Automated Mode, duplicates across all existing companies are merged automatically.")

    ### User Notifications for Manual merge
    notify_user_ids = fields.Many2many('res.users', string='Notify Users',
        help='List of users to notify when there are new records to merge',
        domain=lambda self: [('all_group_ids', 'in', self.env.ref('base.group_system').id)])
    notify_frequency = fields.Integer(string='Notify', default=1)
    notify_frequency_period = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months')], string='Notify Frequency Period', default='weeks')
    last_notification = fields.Datetime(readonly=True)

    ### Similarity Threshold
    similarity_threshold = fields.Integer(
        string='Similarity Threshold', default=75,
        help='Manual merge mode: Duplicates with a similarity percentage below this threshold will not be suggested.\n'
             'Automatic merge mode: Duplicates with a similarity percentage above this threshold will be merged automatically.'
    )

    ### Contextual menu action
    is_contextual_merge_action = fields.Boolean(string='Merge action attached', help='If True, this record is used for contextual menu action "Merge" on the target model.')

    _uniq_name = models.Constraint(
        'UNIQUE(name)',
        "This name is already taken",
    )
    _check_notif_freq = models.Constraint(
        'CHECK(notify_frequency > 0)',
        "The notification frequency should be greater than 0",
    )

    @api.depends('res_model_id')
    def _compute_name(self):
        for dm_model in self:
            dm_model.name = dm_model.res_model_id.name if dm_model.res_model_id else ''

    @api.onchange('res_model_id')
    def _onchange_res_model_id(self):
        self._check_prevent_merge()
        if self.res_model_name:
            self.env[self.res_model_name].check_access('read')
        if any(rule.field_id.model_id != self.res_model_id for rule in self.rule_ids):
            self.rule_ids = [(5, 0, 0)]

    @api.onchange('merge_mode')
    def _onchange_merge_mode(self):
        if self.merge_mode == 'automatic':
            return {
                'warning': {
                    'title': "Automatic Mode",
                    'message': "When enabling automatic mode your rules will run periodically without manual validation. "
                               "Please note that these changes are permanent and cannot be reversed."
                }
            }

    def _compute_records_to_merge_count(self):
        count_data = self.env['data_merge.record'].with_context(data_merge_model_ids=tuple(self.ids))._read_group([('model_id', 'in', self.ids)], ['model_id'], ['__count'])
        counts = {model.id: count for model, count in count_data}
        for dm_model in self:
            dm_model.records_to_merge_count = counts[dm_model.id] if dm_model.id in counts else 0

    @api.depends('res_model_name')
    def _compute_custom_merge_method(self):
        for dm_model in self:
            if dm_model.res_model_name:
                dm_model.custom_merge_method = hasattr(self.env[dm_model.res_model_name], '_merge_method')
            else:
                dm_model.custom_merge_method = False

    ############################
    ### Cron / find duplicates
    ############################
    def _notify_new_duplicates(self):
        """
        Notify the configured users when new duplicate records are found.
        The method is called after the identification process and will notify based on the configured frequency.
        """
        for dm_model in self.env['data_merge.model'].search([('merge_mode', '=', 'manual')]):
            if not dm_model.notify_user_ids or not dm_model.notify_frequency:
                continue

            if dm_model.notify_frequency_period == 'days':
                delta = relativedelta(day=dm_model.notify_frequency)
            elif dm_model.notify_frequency_period == 'weeks':
                delta = relativedelta(weeks=dm_model.notify_frequency)
            else:
                delta = relativedelta(months=dm_model.notify_frequency)

            if not dm_model.last_notification or (dm_model.last_notification + delta) < fields.Datetime.now():
                dm_model.last_notification = fields.Datetime.now()
                dm_model._send_notification(delta)

    def _send_notification(self, delta):
        """
        Send a notification to the users if there are duplicates created since today minus `delta`

        :param delta: delta representing the notification frequency
        """
        self.ensure_one()
        last_date = fields.Date.today() - delta
        num_records = self.env['data_merge.record'].search_count([
            ('model_id', '=', self.id),
            ('create_date', '>=', last_date),
        ])
        if num_records:
            partner_ids = self.notify_user_ids.partner_id.ids
            menu_id = self.env.ref('data_recycle.menu_data_cleaning_root').id
            # TDE note: use with_source
            self.env['mail.thread'].sudo().message_notify(
                body=self.env['ir.qweb']._render(
                    'data_cleaning.data_merge_duplicate',
                    dict(
                        num_records=num_records,
                        res_model_label=self.res_model_id.name,
                        model_id=self.id,
                        menu_id=menu_id
                    )
                ),
                model=self._name,
                partner_ids=partner_ids,
                res_id=self.id,
                subject=self.env._('Duplicates to Merge'),
            )

    def _cron_find_duplicates(self):
        """
        Identify duplicate records for each active model and either notify the users or automatically merge the duplicates
        """
        self.env['data_merge.model'].sudo().search([]).find_duplicates(batch_commits=True)
        self._notify_new_duplicates()

    def find_duplicates(self, batch_commits=False):
        """
        Search for duplicate records and create the data_merge.group along with its data_merge.record

        :param bool batch_commits: If set, will automatically commit every X records
        """
        unaccent = self.env.registry.unaccent
        self.env.flush_all()
        for dm_model in self:
            t1 = timeit.default_timer()
            ids = []
            current_valid_ids = set()
            res_model = self.env[dm_model.res_model_name]

            for rule in dm_model.rule_ids:
                domain = ast.literal_eval(dm_model.domain or '[]')
                query = res_model._search(domain, bypass_access=True)
                if rule.field_id.relation:
                    related_table = query.table._join(rule.field_id.name, kind='JOIN')
                    sql_field = related_table[related_table._model._rec_name]
                else:
                    sql_field = query.table[rule.field_id.name]

                if rule.match_mode == 'accent':
                    # Since unaccent is case sensitive, we must add a lower to make sql_field insensitive
                    sql_field = unaccent(SQL('lower(%s)', sql_field))

                sql_group_by = SQL()
                multi_company = self.env['res.company'].with_context(active_test=False).search_count([]) > 1
                company_field = res_model._fields.get('company_id')
                if multi_company and company_field and not dm_model.mix_by_company:
                    sql_group_by = SQL(', %s', query.table.company_id)

                # Get all the rows matching the rule defined
                # (e.g. exact match of the name) having at least 2 records
                # Each row contains the matched value and an array of matching records:
                #   | value matched | {array of record IDs matching the field}
                sql = SQL(
                    """
                    SELECT %(field)s AS group_field_name,
                        array_agg(%(table_id)s ORDER BY %(table_id)s ASC)
                    FROM %(tables)s
                    WHERE length(%(field)s) > 0 AND %(where_clause)s
                    GROUP BY group_field_name %(group_by)s
                    HAVING COUNT(%(field)s) > 1
                    """,
                    field=sql_field,
                    table_id=query.table.id,
                    tables=query.from_clause,
                    where_clause=query.where_clause or SQL("TRUE"),
                    group_by=sql_group_by,
                )

                try:
                    self.env.cr.execute(sql)
                except psycopg2.errors.UndefinedFunction:
                    raise UserError(self.env._('Missing required PostgreSQL extension: unaccent')) from None

                rows = self.env.cr.fetchall()
                for row in rows:
                    current_valid_ids.update(row[1])
                    ids.append(row[1])

            # Remove previously created duplicate records that no longer
            # match any deduplication rule to keep groups updated.
            domain = [('model_id', '=', dm_model.id)]
            if current_valid_ids:
                # we only keep the records which are still valid according to the rules,
                # so we remove the ones which are not in the current_valid_ids list
                domain.append(('res_id', 'not in', current_valid_ids))
            self.env['data_merge.record'].search(domain).unlink()

            # Fetches the IDs of all the records who already matched (and are not merged),
            # as well as the discarded ones.
            # This prevents creating twice the same groups.
            self.env.cr.execute("""
                SELECT
                    group_id,
                    ARRAY_AGG(res_id ORDER BY res_id ASC)
                FROM data_merge_record
                WHERE model_id = %s
                GROUP BY group_id""", [dm_model.id])

            existing_groups = {
                group_id: set(res_ids)
                for group_id, res_ids in self.env.cr.fetchall()
            }

            _logger.info('Query identification done after %s' % str(timeit.default_timer() - t1))
            t1 = timeit.default_timer()
            if self.env['ir.config_parameter'].get_bool('data_merge.merge_lists', True):
                merge_list = merge_common_lists
            else:
                merge_list = lambda x: x
            groups_to_create = [set(r) for r in merge_list(ids) if len(r) > 1]
            _logger.info('Merging lists done after %s' % str(timeit.default_timer() - t1))
            t1 = timeit.default_timer()
            _logger.info('Record creation started at %s', str(t1))
            groups_created = 0
            groups_to_create_count = len(groups_to_create)
            for group_to_create in groups_to_create:
                groups_created += 1
                if groups_created % 100 == 0:
                    _logger.info('Created groups %s / %s' % (groups_created, groups_to_create_count))

                # Check if the IDs of the group to create is already part of an existing group
                # e.g.
                #   The group with records A B C already exists:
                #       1/ If group_to_create equals A B, do not create a new group
                #       2/ If group_to_create equals A D, create the new group (A D is not a subset of A B C)
                #       3/ If group_to_create equals A B C D, add D to the existing group A B C

                matched_group_id = None
                skip_creation = False

                for group_id, existing_ids in existing_groups.items():
                    # If the group to create is already part of an existing group, we skip the creation (case 1)
                    if group_to_create <= existing_ids:
                        skip_creation = True
                        break

                    # If the group to create has common records with an existing group, we add the missing records to this existing group (case 3)
                    if existing_ids <= group_to_create:
                        matched_group_id = group_id
                        break

                if skip_creation:
                    continue

                if matched_group_id:
                    missing_ids = group_to_create - existing_groups[matched_group_id]
                    if missing_ids:
                        # Since the group already exists, we only create the missing records for the new group and link them to the existing group.
                        self.env['data_merge.record'].create([
                            {'group_id': matched_group_id, 'res_id': res_id}
                            for res_id in missing_ids
                        ])
                        existing_groups[matched_group_id].update(missing_ids)
                    continue

                group = self.env['data_merge.group'].with_context(prefetch_fields=False).create({'model_id': dm_model.id})
                d = [{'group_id': group.id, 'res_id': rec} for rec in group_to_create]
                self.env['data_merge.record'].with_context(prefetch_fields=False).create(d)

                if groups_created % DR_CREATE_STEP_AUTO == 0 and batch_commits:
                    self.env.cr.commit()

                group._elect_master_record()

                if group.similarity * 100 < dm_model.similarity_threshold:
                    group.unlink()

            _logger.info('Record creation done after %s' % str(timeit.default_timer() - t1))

            if dm_model.merge_mode == 'automatic' and not self.env.context.get('manual_find_duplicates_trigger', False):
                existing_groups = self.env['data_merge.group'].search([
                    ('model_id', '=', dm_model.id),
                    ('similarity', '>=', dm_model.similarity_threshold / 100.0),
                ])
                for idx in range(0, len(existing_groups), DR_CREATE_STEP_AUTO):
                    existing_batch = existing_groups[idx:idx + DR_CREATE_STEP_AUTO]
                    for group in existing_batch:
                        group.merge_records()
                    existing_batch.unlink()
                    if batch_commits and not modules.module.current_test:
                        self.env.cr.commit()

    ##############
    ### Overrides
    ##############
    @api.constrains('res_model_id')
    def _check_prevent_merge(self):
        models = set(self.env['ir.model'].browse(self.res_model_id.ids).mapped('model'))
        for model_name in models:
            if model_name and hasattr(self.env[model_name], '_prevent_merge') and self.env[model_name]._prevent_merge:
                raise ValidationError(self.env._('Deduplication is forbidden on the model: %s', model_name))

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            self.env['data_merge.group'].search([('model_id', 'in', self.ids)]).unlink()

        similarity_threshold = vals.get('similarity_threshold')
        if similarity_threshold is not None:
            self.env['data_merge.group'].search(
                [('model_id', 'in', self.ids), ('similarity', '<=', similarity_threshold / 100)]).unlink()

        return super().write(vals)

    def unlink(self):
        if self.ids:
            self.env["mail.message"].search(
                [("model", "=", "data_merge.model"), ("res_id", "in", self.ids)]
            ).sudo().unlink()
        return super().unlink()

    #############
    ### Actions
    #############
    def open_records(self):
        self.ensure_one()

        action = self.env["ir.actions.actions"]._for_xml_id("data_cleaning.action_data_merge_record")
        action['context'] = dict(ast.literal_eval(action.get('context')), searchpanel_default_model_id=self.id)
        return action

    def action_find_duplicates(self):
        self.sudo().with_context(manual_find_duplicates_trigger=True).find_duplicates()
        return self.open_records()

    def refresh_duplicates_records(self):
        """
        Refresh duplicate records and reopen the Data Merge view.
        Preserves the selected search panel rule by passing `model_id`
        from the domain into the action context.
        """
        self.search([]).find_duplicates(batch_commits=True)
        model_id = self.env.context.get('model_id')
        action = self.env["ir.actions.actions"]._for_xml_id("data_cleaning.action_data_merge_record")
        context = action.get('context', {})
        if isinstance(context, str):
            context = ast.literal_eval(context)
        if model_id:
            context['searchpanel_default_model_id'] = model_id
        action['context'] = context
        action['target'] = 'main'
        return action
