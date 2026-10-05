from odoo import api, models
from odoo.fields import Domain


class AnalyticMixin(models.AbstractModel):
    _inherit = 'analytic.mixin'

    @api.model
    def _read_group_for_accrual(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[tuple]:
        """ This method is called instead of usual `_read_group` to compute the
        sum of non-storedcomputed fields. It's used in the accrual views,
        by `purchase.order.line` and `sale.order.line` models.
        """
        aggregates_to_skip, fields_to_patch = self._get_aggregates_to_skip_and_fields_to_patch()
        fields_index = {}
        for field in fields_to_patch:
            field_aggregate = f'{field}:sum'
            if field_aggregate in aggregates:
                fields_index[field] = aggregates.index(field_aggregate)
        if not fields_index.keys():
            return super()._read_group(domain, groupby, aggregates, having, offset, limit, order)

        aggregates_2_0 = tuple(a for a in aggregates if a not in aggregates_to_skip)
        res = super()._read_group(domain, groupby, aggregates_2_0, having, offset, limit, order)

        # Make the aggregate sum "manually".
        # Pre-fetch all matching records once outside the loop to avoid re-evaluating
        # expensive search methods on every group iteration.
        field_name = groupby[0]
        date_granularity = ''
        if ':' in field_name:
            # Support of group by date fields.
            field_name, date_granularity = field_name.split(':')

        all_records = self.env[self._name].search_fetch(
            domain=Domain.AND([domain, self._get_accrual_domain()]),
            field_names=[field_name],
        )
        if date_granularity:
            records_by_group = dict(
                all_records._read_group(
                    domain=[('id', 'in', all_records.ids)],
                    groupby=groupby,
                    aggregates=['id:recordset'],
                )
            )
        else:
            records_by_group = all_records.grouped(field_name)

        patched_res = []
        for group in res:
            records = records_by_group.get(group[0], all_records.browse())
            new_tuple = list(group)
            for field, index in fields_index.items():
                sum_qty_received = sum(rec[field] for rec in records)
                new_tuple.insert(index + 1, sum_qty_received)
            patched_res.append(tuple(new_tuple))
        return patched_res

    @api.model
    def _get_aggregates_to_skip_and_fields_to_patch(self):
        return (
            ['qty_invoiced_at_date:sum', 'amount_to_invoice_at_date:sum'],
            ['qty_invoiced_at_date', 'amount_to_invoice_at_date']
        )


AnalyticMixin._read_group_for_accrual.__override__ = False  # whitelist super()
