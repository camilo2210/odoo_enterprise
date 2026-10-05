# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.models import MAGIC_COLUMNS
from odoo.tools import split_every
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

IGNORED_FIELDS = MAGIC_COLUMNS
DM_CRON_BATCH_SIZE = 100


class Data_MergeGroup(models.Model):
    _name = 'data_merge.group'
    _description = 'Deduplication Group'
    _order = 'similarity desc'

    active = fields.Boolean(default=True)
    model_id = fields.Many2one('data_merge.model', string='Deduplication Model', ondelete='cascade', required=True)
    res_model_id = fields.Many2one(related='model_id.res_model_id', store=True, readonly=True)
    res_model_name = fields.Char(related='model_id.res_model_name', store=True, readonly=True)
    similarity = fields.Float(
        string='Similarity %', readonly=True, store=True, compute='_compute_similarity',
        help='Similarity coefficient based on the amount of text fields exactly in common.')
    divergent_fields = fields.Char(
        compute='_compute_similarity', store=True)
    record_ids = fields.One2many('data_merge.record', 'group_id')

    @api.depends('model_id', 'similarity')
    def _compute_display_name(self):
        for group in self:
            group.display_name = self.env._('%(model)s - Similarity: %(similarity)s%%', model=group.model_id.name, similarity=int(group.similarity * 100))

    def _get_similarity_fields(self):
        self.ensure_one()
        group_fields = self.env[self.res_model_name]._fields.items()
        return [name for name, field in group_fields if field.type == 'char']

    @api.depends('record_ids')
    def _compute_similarity(self):
        for group in self:
            if not group.record_ids:
                group.divergent_fields = ''
                group.similarity = 1
                continue

            read_fields = group._get_similarity_fields()

            record_ids = group.record_ids.mapped('res_id')
            records = self.env[group.res_model_name].browse(record_ids).read(read_fields)
            # YTI What about unaccent ? Should be taken into account IMO if the
            # rule was computed from that.
            data = set(records[0].items())
            data = data.intersection(*[set(record.items()) for record in records[1:]])

            diff_fields = set(read_fields) - {k for k, v in data}  # fields of the model minus the identical fields
            group.divergent_fields = ','.join(diff_fields)
            group.similarity = min(1, len(data) / len(read_fields))

    def discard_records(self, records=None):
        domain = Domain('group_id', '=', self.id)

        if records is not None:
            domain &= Domain('id', 'in', records)
        self.env['data_merge.record'].search(domain).write({'is_discarded': True, 'is_master': False})
        if all(not record.active for record in self.record_ids):
            self.active = False
        self._elect_master_record()

    def undiscard_records(self, records=None):
        domain = Domain('group_id', '=', self.id)

        if records is not None:
            domain &= Domain('id', 'in', records)

        records_to_restore = self.env['data_merge.record'].with_context(active_test=False).search(domain)
        records_to_restore.write({'is_discarded': False})

        all_group_records = self.with_context(active_test=False).record_ids
        if any(record.active for record in all_group_records):
            self.active = True
        self._elect_master_record()

    ###################
    ### Master Record
    ###################
    def _elect_master_record(self):
        """
        Elect the "master" record.

        This method will look for a `_elect_method()` on the model.
        If it exists, this method is responsible to return the master record, otherwise, a generic method is used.
        """
        for group in self:
            records = group.record_ids._original_records()
            if not records:
                return

            elect_master = group._get_elect_master_method()
            master = elect_master(records)
            if master:
                master_record = group.record_ids.filtered(lambda r: r.res_id == master.id)
                master_record.is_master = True

    ## Generic master
    def _elect_method(self, records):
        """
        Generic master election method.

        :param records: all the records of the duplicate group
        :return the oldest record as master
        """
        records_sorted = records.sorted('create_date')
        return records_sorted[0] if records_sorted else None

    def _get_elect_master_method(self):
        """Return the method used to elect the master record.
        If the target model defines a custom `_elect_method`, it is returned.
        Otherwise, the default generic method is used.
        """
        self.ensure_one()
        model = self.env[self.res_model_name]
        if hasattr(model, "_elect_method"):
            return model._elect_method

        return self._elect_method

    ###########
    ### Merge
    ###########
    @api.model
    def merge_multiple_records(self, group_records):
        group_records = {int(k): v for k, v in group_records.items()}
        group_ids = self.browse(group_records.keys())

        for group in group_ids:
            group.merge_records(group_records[group.id])

    def merge_records(self, records=None):
        """
        Merge the selected records.

        This method will look for a `_merge_method()` on the model.
        If it exists, this method is responsible to merge the records, otherwise, the generic method is used.

        :param records: Group records to be merged, or None if all records should be merged
        """
        self.ensure_one()
        if records is None:
            records = []

        domain = [('group_id', '=', self.id)]
        if records:
            domain += [('id', 'in', records)]

        to_merge = self.env['data_merge.record'].with_context(active_test=False).search(domain, order='id')
        to_merge_count = len(to_merge)
        if to_merge_count <= 1:
            return
        master_record = to_merge.filtered('is_master') or to_merge[0]
        to_merge = to_merge - master_record

        if not master_record._original_records():
            _logger.warning('The master record does not exist')
            return

        _logger.info('Merging %s records %s into %s' % (self.res_model_name, to_merge.mapped('res_id'), master_record.res_id))

        model = self.env[self.res_model_name]
        if hasattr(model, '_merge_method'):
            merge = model._merge_method
        else:
            merge = self._merge_method

        # Create a dict with chatter data, in case the merged records are deleted during the merge procedure
        chatter_data = {rec.res_id:dict(res_id=rec.res_id, merged_record=str(rec.name), changes=rec._record_snapshot()) for rec in to_merge}
        res = merge(master_record._original_records(), to_merge._original_records())
        if res.get('error'):
            if self.model_id.merge_mode == 'automatic':
                _logger.warning('Error occurred while merging records for group %s: %s', self.id, res['error'])
                return
            raise UserError(res['error'])
        if res.get('log_chatter'):
            self._log_merge(master_record, to_merge, chatter_data)

        if res.get('post_merge'):
            self._post_merge(master_record, to_merge)

        is_merge_action = master_record.model_id.is_contextual_merge_action
        (master_record + to_merge).unlink()

        return {
            'records_merged': res['records_merged'] if res.get('records_merged') else to_merge_count,
            # Used to get back to the functional model if deduplicate was
            # called from contextual action menu - instead of staying on
            # the deduplicate view.
            'back_to_model': is_merge_action
        }

    def _log_merge(self, master_record, merged_records, chatter_data):
        """
        Post a snapshot of each merged records on the master record
        """
        if not isinstance(self.env[self.res_model_name], self.env.registry['mail.thread']):
           return

        values = {
            'res_model_label': self.res_model_id.name,
            'res_model_name': self.res_model_name,
            'res_id': master_record.res_id,
            'master_record': master_record.name,
        }
        for rec in merged_records:
            master_values = chatter_data.get(rec.res_id, {})
            master_values.update({
                'res_model_label': self.res_model_id.name,
                'res_model_name': self.res_model_name,
                'archived': rec._original_records().exists(),
            })
            if self.model_id.removal_mode == 'archive':
                rec._original_records()._message_log_with_view('data_cleaning.data_merge_merged', render_values=values)
            master_record._original_records()._message_log_with_view('data_cleaning.data_merge_main', render_values=master_values)


    ## Generic Merge
    def _merge_method(self, master, records):
        """
        Generic merge method, will "only" update the foreign keys from the source records to the master record

        :param master: original record considered as the destination
        :param records: source records to be merged with the master
        :return dict
        """
        self.env['data_merge.record']._update_foreign_keys(destination=master, source=records)

        return {
            'post_merge': True, # Perform post merge activities
            'log_chatter': True # Log merge notes in the chatter
        }

    def _post_merge(self, master, records):
        """
        Perform the post merge activities such as archiving or deleting the original record
        """
        origins = records._original_records()
        if self.model_id.removal_mode == 'delete' or not origins._active_name:
            origins.unlink()
        else:
            origins.write({origins._active_name: False})

    ##########
    ### Cron
    ##########
    def _cron_cleanup(self, auto_commit=True):
        """ Perform cleanup activities for each data_merge.group. """
        groups = self.with_context(active_test=False).env['data_merge.group'].search([])

        for batched_groups in split_every(DM_CRON_BATCH_SIZE, groups.ids, self.with_context(active_test=False).browse):
            batched_groups._cleanup()

            if auto_commit:
                self.env.cr.commit()

    def _cleanup(self):
        """
        Do the cleanup, it will delete:
            - merged data_merge.record
            - data_merge.record with archived or deleted original record
            - data_merge.group with 0 or 1 data_merge.record
        """
        records_to_delete = self.env['data_merge.record']
        groups_to_delete = self.env['data_merge.group']

        for group in self:
            # Count the records kept per group and if there are discarded records
            records_discarded = False
            records_kept = 0

            # Delete records no longer existing
            original_records = {r.id: r for r in group.record_ids._original_records()} if group.record_ids else {}
            # Delete group if all original records in a group have been deleted
            if not original_records:
                groups_to_delete += group
                continue

            for rec in group.record_ids:
                original_record = original_records.get(rec.res_id)
                if not original_record:
                    records_to_delete += rec
                    continue

                origin_inactive = (original_record._active_name and not original_record[original_record._active_name])
                if origin_inactive:
                    records_to_delete += rec
                    continue

                records_discarded = records_discarded or rec.is_discarded
                if not rec.is_discarded:
                    records_kept += 1

            # Delete groups with at most 1 record and no discarded records
            if not records_discarded and records_kept <= 1:
                groups_to_delete += group

            # Delete single non-discarded record in groups with discarded record(s)
            if records_discarded and records_kept == 1:
                records_to_delete += group.record_ids.filtered(lambda r: not r.is_discarded)

        records_to_delete.unlink()
        groups_to_delete.unlink()

    ##########
    ### Merge Preview
    ##########
    def _get_deduplication_rule_mapping(self, master_rec, source_rec):
        """ Return the values of the fields used in deduplication rules for the master and source records.
        :param master_rec: `data_merge.record` destination record
        :param source_rec: `data_merge.record` source record
        :return: Dict of field labels with their corresponding values for master and source records,
                and whether they match or not.
        """
        self.ensure_one()
        rule_lines = self.model_id.rule_ids
        rule_field_names = rule_lines.mapped('field_id.name')

        # _render_values returns {field_description: formatted_value} if value exists for the field.
        master_vals = master_rec._render_values(rule_field_names)
        source_vals = source_rec._render_values(rule_field_names)

        rule_fields = {}
        for field_label in rule_lines.mapped('field_id.field_description'):
            master_value = master_vals.get(field_label)
            source_value = source_vals.get(field_label)

            rule_fields[field_label] = {
                "master_value": master_value,
                "source_value": source_value,
                "is_match": str(master_value).lower() == str(source_value).lower()
            }

        return rule_fields

    def _get_field_preview(self, master_rec, master, source_rec, source):
        """Prepare a field-by-field diff for all fields whose values differ between master and source.
        If the model provides a `_get_merge_result_values` method, use it to know which values
        will update the master. Otherwise, keep the value of the master and ignore the source.

        :param master_rec: `data_merge.record` destination record
        :param master: original destination record
        :param source_rec: `data_merge.record` source record
        :param source: original source record
        :return: list of dictionaries describing field merge
        """
        self.ensure_one()
        model = self.env[self.res_model_name]
        # Divergent fields contain field names whose values differ across group records
        divergent = self.divergent_fields.split(',') if self.divergent_fields else []
        master_div = master_rec._render_values(divergent)
        source_div = source_rec._render_values(divergent)

        # If the model has a `_get_merge_result_values` method, use it to determine which values update the master.
        values_update_in_master = model._get_merge_result_values(master, source) if hasattr(model, "_get_merge_result_values") else {}

        field_preview = []
        for field_label in (master_div.keys() | source_div.keys()):
            master_val = master_div.get(field_label)
            source_val = source_div.get(field_label)
            # Skip rows where both values are same.
            if master_val == source_val:
                continue

            # Check if the source value will replace the master value after merge
            # Example: if master_val is empty and source_val is "John", master_val will be updated to "John" and highlighted in the preview
            will_update = field_label in values_update_in_master and values_update_in_master[field_label] != master_val

            field_preview.append({
                "field_label": field_label,
                "master_value": master_val,
                "source_value": source_val,
                "will_update_master": will_update,
            })
        return field_preview

    def _get_relation_preview(self, master_rec, source_rec):
        """Compute relational impact preview when merging source rec into master.
        This method compares how many records are linked to the master and
        source records across different models and fields. These relations
        will be merged into the master after the merge.

        :param master_rec: target `data_merge.record`.
        :param source_rec: source `data_merge.record` to merge.
        :return: List of dict describing the models and fields linked to the master and source records, and their count.
        """
        self.ensure_one()
        # Get all linked records of master and source
        # Returns {record.id: [(count, model_label, model, field_name), ...]}
        record_ref = (master_rec + source_rec)._get_references()
        master_map, source_map = {}, {}  # {(model, model_label, field_name): count}

        for count, model_label, model, field_name in record_ref.get(master_rec.id):
            master_map[model, model_label, field_name] = count

        for count, model_label, model, field_name in record_ref.get(source_rec.id):
            source_map[model, model_label, field_name] = count

        merged_relations = []
        for key in (master_map.keys() | source_map.keys()):
            model, model_label, field_name = key

            merged_relations.append({
                "model": model,
                "model_label": model_label,
                "field_name": field_name,
                "master_count": master_map.get(key, 0),
                "source_count": source_map.get(key, 0),
            })
        return merged_relations

    @api.model
    def _get_image_url(self, record, image_field):
        return f"/web/image/{record._name}/{record.id}/{image_field}"

    @api.model
    def _get_record_name(self, record):
        """Return the display name of records excepts for res.partner where we return name and
        company_name separately to ease
        """
        # For contacts, display contact name first, then company/group.
        if self.res_model_name != 'res.partner':
            return record.display_name, False
        company_name = record.parent_id.commercial_partner_id.display_name
        return record.name, company_name

    def get_merge_preview(self, record_id):
        """Return merge preview information for the selected source record.

        :param record_id: ID of the source `data_merge.record`
        :return: dict containing merge preview data
        """
        self.ensure_one()
        active_records = self.record_ids.filtered(lambda r: not r.is_discarded)
        if not active_records:
            return {}
        source_rec, master_rec = None, None
        for record in active_records:
            if record.id == record_id:
                source_rec = record
            if record.is_master:
                master_rec = record
            if master_rec and source_rec:
                break
        if not source_rec:
            return {}

        # Compute the master record if it is not already selected.
        if not master_rec:
            elect_master = self._get_elect_master_method()
            master = elect_master(active_records._original_records())
            if not master:
                return {}
            master_rec = active_records.filtered(lambda r: r.res_id == master.id)
        else:
            master = master_rec._original_records()
        source = source_rec._original_records()

        model = self.env[self.res_model_name]
        image_field = model._fields.get('avatar_128') and 'avatar_128' or model._fields.get('image_128') and 'image_128'

        master_name, master_company_name = self._get_record_name(master)
        source_name, source_company_name = self._get_record_name(source)
        return {
            "master_id": master.id,
            "source_id": source.id,
            "master_name": master_name,
            "source_name": source_name,
            "master_company_name": master_company_name,
            "source_company_name": source_company_name,
            "master_image_url": image_field and self._get_image_url(master, image_field),
            "source_image_url": image_field and self._get_image_url(source, image_field),
            "deduplication_rule_mapping": self._get_deduplication_rule_mapping(master_rec, source_rec),
            "master_exclusive": self._get_field_preview(master_rec, master, source_rec, source),
            "merged_relations": self._get_relation_preview(master_rec, source_rec),
        }
