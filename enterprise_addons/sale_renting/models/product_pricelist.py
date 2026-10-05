# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import timedelta
from functools import partial

from odoo import fields, models
from odoo.fields import Domain
from odoo.tools.sql import SQL

from odoo.addons.sale_renting import utils


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def _compute_price_rule(
        self, products, quantity, *, start_date=None, end_date=None, depth=0, **kwargs
    ):
        """Override to handle the rental product prices.

        .. seealso:: :meth:`_compute_rental_price_rule`

        :param datetime|None start_date: Start of the rental period.
        :param datetime|None end_date: End of the rental period.
        :param int depth: Technical flag to avoid multiplying the quantity twice with the number of
            periods in the rental duration. seealso:`product.pricelist.item._compute_base_price`
        """
        self and self.ensure_one()  # self is at most one record
        Product = products.browse()

        start_date = start_date or self.env.context.get("start_date")
        end_date = end_date or self.env.context.get("end_date")
        if start_date and end_date:
            rental_products = products.filtered("rent_periodicity")
        else:
            # Fall back on the sales prices
            rental_products = Product

        results = super()._compute_price_rule(
            products - rental_products, quantity, depth=depth, **kwargs
        )

        groups = rental_products.grouped("rent_periodicity")
        if "nights" in groups:
            groups["days"] = groups.get("days", Product) + groups.pop("nights", Product)
        for periodicity_unit, rental_products_group in groups.items():
            if not depth:
                # Multiply by the number of periods for the ``min_quantity`` condition
                quantity_to_consider = quantity * utils.number_of_periods(
                    periodicity_unit, start_date, end_date
                )
            else:
                # Avoid multiplying twice in case of base pricelist price computation
                quantity_to_consider = quantity

            results.update(
                self._compute_rental_price_rule(
                    rental_products_group,
                    quantity_to_consider,
                    periodicity_unit,
                    start_date,
                    end_date,
                    depth=depth,
                    **kwargs,
                )
            )

        return results

    def _compute_rental_price_rule(
        self, products, quantity, periodicity_unit, start_date, end_date, **kwargs
    ):
        """Compute rental prices for products over a given period.

        The rental price for each product is computed as the sum of the price at each periodicity
        step (``start_date + n * periodicity``) during the given rental period.

        Example::

            | Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday |
            |                list price applies                   | +50% surcharge |

        If we rent by days from Tuesday (start of day) to Sunday (end of day), the total is 5 days
        at the list price and 1 day with a 50% surcharge. This is because the surcharge rule had not
        started yet when the periodicity step was evaluated (at midnight).

        The rule for a rental product is always ``False`` because the final amount may aggregate
        multiple applicable pricing rules over time.

        :param product.product|product.template products: Rental products.
        :param float quantity: Ordered quantity.
        :param str periodicity_unit: The rented periodicity as a delta unit, (hours/days/weeks).
        :param datetime start_date: Start of the rental period.
        :param datetime end_date: End of the rental period.
        :param dict kwargs: Arguments forwarded to :meth:`_resolve_applicable_rule_and_price`.
        :return: Rental price and corresponding rule per product ID.
        :rtype: dict[int, tuple[float, Literal[False]]]
        """
        self and self.ensure_one()  # self is at most one record

        if not (kwargs.get("compute_price", True) and products and start_date < end_date):
            return {product.id: (0.0, False) for product in products}

        # Set required arguments of :meth:`_resolve_applicable_rule_and_price`
        kwargs.setdefault("date", fields.Datetime.now())  # Conversion date

        # For each product, we accumulate the total by iterating over stable validity intervals,
        # pricing each interval with the active rules. Because an interval is not always an exact
        # multiple of `periodicity`, we keep a start cursor to track how much time was already
        # consumed to prevent counting the same periodicity step more than once.

        applicable_rules_by_interval = self._search_stable_intervals_of_applicable_rules(
            products, start_date, end_date, quantity=quantity, **kwargs
        )
        aggregated_prices = defaultdict(float)
        start_cursor = start_date

        for (_, end), rules in applicable_rules_by_interval:
            number_of_periods = max(utils.number_of_periods(periodicity_unit, start_cursor, end), 0)

            # If `start_cursor` goes beyond the end of the current interval, prices have already
            # been computed in the previous interval.
            if number_of_periods:
                results = self._resolve_applicable_rule_and_price(
                    rules, products, quantity, start_date=start_cursor, end_date=end, **kwargs
                )
                for product_id, (price, _rule_id) in results.items():
                    aggregated_prices[product_id] += price

            # Advance by multiples of `periodicity`
            start_cursor += timedelta(**{periodicity_unit: number_of_periods})

        return {product_id: (price, False) for product_id, price in aggregated_prices.items()}

    def _search_stable_intervals_of_applicable_rules(
        self, products, start_date, end_date, /, **kwargs
    ):
        """Return intervals where the set of applicable rules is stable.

        A stable interval is a maximal sub-interval of ``[start_date, end_date]`` where the set of
        applicable rules does not change.

        :param product.product|product.template products: Products/templates used to build the base
            applicability domain.
        :param datetime start_date: Start of the rental period.
        :param datetime end_date: End of the rental period.
        :param dict kwargs: Extra arguments forwarded to :meth:`_get_applicable_rules_domain`,
            except ``date``.
        :return: Pairs of interval and corresponding rules, ordered by interval.
        :rtype: list[tuple[tuple[datetime, datetime], product.pricelist.item]]
        """
        PricelistRule = self.env["product.pricelist.item"]
        kwargs.pop("date", None)  # Ignore the date as we will be looking at a range

        if not self:
            # Without a pricelist, the applicable-rule domain can collapse to `Domain.FALSE`
            # (`pricelist_id = False`). Skip the SQL query and return no rules.
            return [((start_date, end_date), PricelistRule)]

        self.ensure_one()
        domain = self._get_applicable_rules_domain(
            products, start_date=start_date, end_date=end_date, **kwargs
        )

        applicable_rule_query = PricelistRule._search(domain, order=PricelistRule._order)
        pricelist_rule_table = applicable_rule_query.table
        applicable_rule_sql = applicable_rule_query.select(
            pricelist_rule_table.id, pricelist_rule_table.date_start, pricelist_rule_table.date_end
        )

        query = SQL(
            """
            WITH applicable_rule AS (%(applicable_rule)s),
            -- Compute all distinct instants within `start_date` and `end_date` where the set of
            -- applicable rules changes.
            instant(date) AS (
                 SELECT DISTINCT rule.date_start
                   FROM applicable_rule rule
                  WHERE rule.date_start > %(start_date)s
                  UNION
                 SELECT DISTINCT rule.date_end
                   FROM applicable_rule rule
                  WHERE rule.date_end < %(end_date)s
                  UNION
                 SELECT DISTINCT * FROM (VALUES (%(start_date)s), (%(end_date)s))
            ),
            -- Compute all intervals in between `start_date` and `end_date` during which the set of
            -- applicable rules remains unchanged.
            interval(start_date, end_date) AS (
                 SELECT interval.start_date, interval.end_date
                   FROM (
                             SELECT i.date AS start_date,
                                    LEAD(i.date) OVER (ORDER BY i.date) AS end_date
                               FROM instant i
                        ) AS interval
                  WHERE interval.end_date IS NOT NULL
               ORDER BY interval.start_date
            )
            -- Select all applicable rules whose validity period intersects with each interval.
             SELECT interval.start_date,
                    interval.end_date,
                    ARRAY(
                         SELECT rule.id
                           FROM applicable_rule rule
                          WHERE COALESCE(rule.date_start, %(start_date)s) < interval.end_date
                            AND COALESCE(rule.date_end, %(end_date)s) > interval.start_date
                    ) AS rule_ids
               FROM interval
            """,
            applicable_rule=applicable_rule_sql,
            start_date=start_date,
            end_date=end_date,
        )

        result = self.env.execute_query(query)
        all_rule_ids = {rule_id for *_interval, rule_ids in result for rule_id in rule_ids}

        browse = partial(
            self.env.registry[PricelistRule._name], self.env, prefetch_ids=tuple(all_rule_ids)
        )
        return [(interval, browse(tuple(rule_ids))) for *interval, rule_ids in result]

    def _get_applicable_rules_domain(self, *args, start_date=None, end_date=None, **kwargs):
        """Extend the base domain to rules whose validity intersects ``[start_date, end_date]``.

        Note: ``date`` and ``start_date/end_date`` are not compatible.

        :param datetime|None start_date: Start of the rental period.
        :param datetime|None end_date: End of the rental period.
        """
        domain = super()._get_applicable_rules_domain(
            *args, start_date=start_date, end_date=end_date, **kwargs
        )

        if start_date and end_date:
            assert not kwargs.get("date"), "Incompatible arguments"
            domain &= Domain.AND([
                Domain("date_start", "=", False) | Domain("date_start", "<=", end_date),
                Domain("date_end", "=", False) | Domain("date_end", ">=", start_date),
            ])

        return domain
