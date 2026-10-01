from odoo import api, fields, models
from odoo.fields import Domain

from odoo.addons.resource.models.utils import extract_comodel_domain


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def _get_gantt_data_with_empty(
        self,
        # we need the caller's parent's get_gantt_data to respect inheritance,
        # otherwise, simply using super().get_gantt_data() would call base's
        # get_gantt_data()
        get_gantt_data,
        # all these parameters are the same as the ones passed to get_gantt_data()
        domain, groupby, read_specification, limit,
        offset, unavailability_fields, progress_bar_fields, start_date,
        stop_date, scale,
    ):
        """
        get_gantt_data(), when grouped by a relation field (e.g.: employee_id),
        does not show the records without a relation to self's model (e.g: does
        not show employees that don't have leaves)

        This function is the equivalent to get_gantt_data(), but it keeps the
        records that don't have any relation to self's model
        """
        if not groupby:
            raise ValueError(self.env._("Cannot group by record if no groupby is specified"))
        if len(groupby) > 1:
            # this is difficult to implement and never needed (for now)
            raise NotImplementedError("Keeping empty records when grouping by multiple fields is not supported")
        if not (field := self._fields.get(groupby[0])) or not field.relational:
            # only relational fields are accepted, as they are the only ones
            # that make sense for this function
            raise ValueError(f"Field in groupby must be a valid relation record, got {groupby}")

        domain = Domain(domain)
        group_field_name = groupby[0]
        group_model_name = self[group_field_name]._name

        # some domains are implicitly applied in ir.access.csv files, we also
        # need to convert them to be compatible to the comodel
        access_domain = self._access_domain('read')

        # gets the equivalent of passed domain but that can be applied directly
        # onto `group_model_name`
        adapted_domain = extract_comodel_domain(self, domain & access_domain, group_field_name)

        # now that we know the domain that will filter out the grouped field, we
        # can know all the ids of the records that will appear on the page
        records_on_page = self.env[group_model_name].search_read(adapted_domain, ['id', 'name'], offset=offset, limit=limit)
        record_on_page_ids = [record['id'] for record in records_on_page]

        # gantt_data will be missing the records that don't belong to any record
        # of self (e.g.: employees without leave if `self` is 'hr.leave')
        gantt_data = get_gantt_data(
            domain & Domain(group_field_name, 'in', record_on_page_ids),
            groupby, read_specification,
            unavailability_fields=unavailability_fields,
            progress_bar_fields=progress_bar_fields, start_date=start_date,
            stop_date=stop_date, scale=scale,
        )

        # since the page is incomplete (gantt_data is missing the records that
        # don't belong to any record of self), we should add them manually
        gantt_records_per_related_field_id = {
            group[group_field_name][0]: group['__record_ids'] for group in gantt_data['groups']
        }
        gantt_data['groups'] = [{
            group_field_name: (record['id'], record['name']),
            '__record_ids': gantt_records_per_related_field_id.get(record['id'], []),
        } for record in records_on_page]

        # this should be the total number of records that can be displayed. It's
        # used in the gantt view for "X to Y of Z records", Z being 'length'
        gantt_data['length'] = self.env[group_model_name].search_count(adapted_domain)

        # fields that don't have records have been added manually, so they may
        # be missing their unavailabilities and progress bar. We thus also have
        # to add those manually
        empty_records_ids = [
            record_id for record_id
            in record_on_page_ids
            if record_id not in gantt_records_per_related_field_id
        ]
        if group_field_name in (unavailability_fields or []):
            gantt_data['unavailabilities'][group_field_name].update(self._gantt_unavailability(
                group_field_name,
                empty_records_ids,
                fields.Datetime.from_string(start_date),
                fields.Datetime.from_string(stop_date),
                scale,
            ))
        if group_field_name in (progress_bar_fields or []):
            gantt_data['progress_bars'][group_field_name].update(self._gantt_progress_bar(
                group_field_name,
                empty_records_ids,
                fields.Datetime.from_string(start_date),
                fields.Datetime.from_string(stop_date),
            ))

        return gantt_data
