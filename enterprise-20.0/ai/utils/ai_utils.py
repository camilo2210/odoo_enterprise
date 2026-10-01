# Part of Odoo. See LICENSE file for full copyright and licensing details.
import ast
import calendar
import enum
import json
import logging
import re
from ast import literal_eval
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from lxml import etree, html
from markupsafe import Markup
from zoneinfo import ZoneInfo
from typing import Any

from odoo.api import Environment
from odoo.models import BaseModel
from odoo.fields import Binary, Command, Image
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, html_sanitize
from odoo.tools.json import json_default
from odoo.tools.mail import html_to_inner_content
from odoo.tools.misc import format_date, format_datetime, submap

from odoo.addons.ai.utils.ai_image_tools import field_to_image_path
from odoo.addons.ai.utils.custom_markdown import CustomMarkdown
from odoo.addons.iap.tools import iap_tools

from .types import AIMessageParts


AI_MODELS_BLOCKLIST = {
    'base.automation',
    'res.device',
    'res.groups',
    'res.groups.privilege',
    'res.users.settings',
}


def is_ai_internal_model(model_name):
    return model_name.startswith('ai.')


VALID_INTERVALS = ['day', 'week', 'month', 'quarter', 'year']
VALID_QUARTERS = ['first_quarter', 'second_quarter', 'third_quarter', 'fourth_quarter']

# Constants for compute_date
QUARTER_MONTHS = {
    1: (1, 2, 3),  # Q1: Jan-Mar
    2: (4, 5, 6),  # Q2: Apr-Jun
    3: (7, 8, 9),  # Q3: Jul-Sep
    4: (10, 11, 12),  # Q4: Oct-Dec
}
MAX_OFFSET = 100
MIN_OFFSET = -100

# Mapping from boundary type to reset dictionaries
BOUNDARY_TIME_RESETS = {
    "start": {
        'minute': {'second': 0, 'microsecond': 0},
        'hour': {'minute': 0, 'second': 0, 'microsecond': 0},
        'day': {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0},
    },
    "end": {
        'minute': {'second': 59, 'microsecond': 999999},
        'hour': {'minute': 59, 'second': 59, 'microsecond': 999999},
        'day': {'hour': 23, 'minute': 59, 'second': 59, 'microsecond': 999999},
    },
}
DEFAULT_ODOO_AI_ENDPOINT = 'https://ai.api.odoo.com'
IAP_TRANSPORT_TIMEOUT = 5
ODOO_AI_COMPLETION_CALLBACK_PATH = '/ai/completion_result_ready'

_logger = logging.getLogger(__name__)


def get_odoo_ai_connection_data(env, add_iap_token=True):
    """Snapshot the ORM-bound IAP connection data into plain scalars."""
    connection = {
        'endpoint': env['ir.config_parameter'].sudo().get_str('ai.endpoint') or DEFAULT_ODOO_AI_ENDPOINT,
    }
    if add_iap_token:
        allowed_company_ids = env.companies.ids
        account = env['iap.account'].sudo().with_context(
            allowed_company_ids=allowed_company_ids,
        ).get('odoo_ai')
        connection['account_token'] = account.account_token
        connection['dbuuid'] = env['ir.config_parameter'].sudo().get_str('database.uuid')
    return connection


def call_odoo_ai_transport(
    connection, route, params, timeout=30, *, raise_user_error=True,
):
    """Call a code-owned IAP route on a snapshotted administrator endpoint."""
    transport_params = dict(params)
    if 'account_token' in connection:
        transport_params['account_token'] = connection['account_token']
        transport_params['dbuuid'] = connection['dbuuid']
    url = f"{connection['endpoint']}/api/odoo_ai/{route}"
    return iap_tools.iap_jsonrpc(
        url,
        params=transport_params,
        timeout=timeout,
        raise_user_error=raise_user_error,
    )


def call_odoo_ai(env, route, params, add_iap_token=True, timeout=60):
    """Call IAP with the current environment's connection settings."""
    connection = get_odoo_ai_connection_data(env, add_iap_token=add_iap_token)
    try:
        return call_odoo_ai_transport(connection, route, params, timeout=timeout)
    except iap_tools.InsufficientCreditError:
        _logger.info("Insufficient credit for Odoo AI")
        from_cron = bool(env.context.get('cron_id'))
        if not from_cron and env.context.get('show_odoo_ai_no_credit_notification', True):
            env['iap.account']._send_no_credit_notification(
                service_name='odoo_ai',
                title=env._("Not enough credits to use Odoo AI"),
            )
        raise


class UserInputResponse(enum.StrEnum):
    """Pre-defined response values for user input requests."""
    CONFIRM_ONCE = 'confirm_once'
    AUTO_CONFIRM = 'auto_confirm'
    DECLINE = 'decline'


def compute_report_measures(fields, field_attrs=None, active_measures=None, sum_aggregator_only=False):
    """
    Python equivalent of the JavaScript computeReportMeasures function.

    Args:
        fields (dict): Dictionary of field definitions from fields_get()
        field_attrs (dict): Dictionary of field attributes with visibility info
        active_measures (list): List of active measure field names
        sum_aggregator_only (bool): Only include fields with 'sum' aggregator

    Returns:
        dict: Ordered dictionary of measures with their field definitions
    """
    if field_attrs is None:
        field_attrs = {}
    if active_measures is None:
        active_measures = []

    # Start with the count measure
    measures = {"__count": {"name": "__count", "string": "Count", "type": "integer"}}

    # Process regular fields
    for field_name, field in fields.items():
        if field_name == "id":
            continue

        # Check if field is invisible
        field_attr = field_attrs.get(field_name, {})
        if field_attr.get("isInvisible", False):
            continue

        # Check if field is numeric and has aggregator
        if field.get("type") in ["integer", "float", "monetary"]:
            aggregator = field.get("aggregator")
            if aggregator:
                if sum_aggregator_only and aggregator != "sum":
                    continue
                # Filter field to only include the keys we want
                filtered_field = submap(field, ["type", "aggregator", "name", "string", "sortable"])
                measures[field_name] = filtered_field

    # Add active measures to the measure list
    # This is rarely necessary, but can be useful for functional fields
    # with overridden read_group methods
    for measure in active_measures:
        if measure not in measures and measure in fields:
            # Filter field to only include the keys we want
            filtered_field = submap(fields[measure], ["type", "aggregator", "name", "string", "sortable"])
            measures[measure] = filtered_field

    # Override field strings from field_attrs if provided
    for field_name, field_attr in field_attrs.items():
        if field_attr.get("string") and field_name in measures:
            measures[field_name] = dict(measures[field_name])
            measures[field_name]["string"] = field_attr["string"]

    # Sort measures: Count is always last, others alphabetically by string
    def sort_key(item):
        field_name, field_def = item
        if field_name == "__count":
            return 1, ""  # Count goes last
        return 0, field_def.get("string", "").lower()

    sorted_measures = sorted(measures.items(), key=sort_key)
    return dict(sorted_measures)


def get_search_view(model, action):
    if action.type != "ir.actions.act_window":
        return None

    return model.get_views(
        [[action.search_view_id.id, "search"]],
        options={"action_id": action.id, "toolbar": False},
    )["views"]["search"]


def serialize_search_view_info(model_fields, search_view_arch):
    """Serialize search view information into a structured text format for AI consumption.

    Returns a text-based representation containing:
    - Searchable fields
    - Filters (grouped by separators)
    - Regular field groupbys
    - Date field groupbys
    """
    if not search_view_arch:
        return ""

    # Parse XML
    tree = etree.fromstring(search_view_arch)

    sections = []

    # 1. Searchable fields
    searchable_fields = []
    for field in tree.xpath(".//field[@name and not(@invisible='1') and not(ancestor::group)]"):
        field_info = {"name": field.get("name")}
        if field.get("string"):
            field_info["string"] = field.get("string")
        if field.get("filter_domain"):
            field_info["filter_domain"] = field.get("filter_domain")
        if field.get("operator"):
            field_info["operator"] = field.get("operator")
        searchable_fields.append(field_info)

    if searchable_fields:
        lines = ["Searchable fields:"]
        for field in searchable_fields:
            field_parts = [field["name"]]
            if "string" in field:
                field_parts.append(field["string"])
            if "filter_domain" in field:
                field_parts.append(f'filter_domain="{field["filter_domain"]}"')
            if "operator" in field:
                field_parts.append(f"operator={field['operator']}")
            lines.append(f"  - {', '.join(field_parts)}")
        sections.append("\n".join(lines))

    # 2. Filters grouped by separators (including date filters)
    filter_groups = []
    current_group = []

    for elem in tree:
        if elem.tag == "separator":
            if current_group:
                filter_groups.append(current_group)
                current_group = []
        elif elem.tag == "filter" and elem.get("name") and elem.get("invisible") != "1":
            if elem.getparent().tag != "group":
                filter_info = {"name": elem.get("name")}
                if elem.get("string"):
                    filter_info["string"] = elem.get("string")

                # Check if this is a date filter
                if elem.get("date"):
                    filter_info["is_date_filter"] = True
                    filter_info["field_name"] = elem.get("date")
                    filter_info["start_year"] = elem.get("start_year", "-2")
                    filter_info["end_year"] = elem.get("end_year", "0")
                    filter_info["start_month"] = elem.get("start_month", "-2")
                    filter_info["end_month"] = elem.get("end_month", "0")

                    # Extract custom options (prefix with "custom_" as done by client)
                    child_filters = elem.xpath("./filter[@name]")
                    if child_filters:
                        filter_info["options"] = [
                            {"name": f"custom_{child.get('name')}", "string": child.get("string")}
                            for child in child_filters
                        ]
                else:
                    # Regular filter
                    if elem.get("domain"):
                        filter_info["domain"] = elem.get("domain")

                current_group.append(filter_info)

    if current_group:
        filter_groups.append(current_group)

    if filter_groups:
        lines = ["Filters:"]
        for group_idx, group in enumerate(filter_groups, 1):
            lines.append(f"  [Group {group_idx}]")
            for filter_item in group:
                if filter_item.get("is_date_filter"):
                    # Date filter: [DATE FILTER] field_name, label, year_range, month_range, options
                    parts = [f"[DATE FILTER] {filter_item['field_name']}"]

                    if "string" in filter_item:
                        parts.append(filter_item["string"])

                    parts.append(f'year_range=[{filter_item["start_year"]} to {filter_item["end_year"]}]')
                    parts.append(f'month_range=[{filter_item["start_month"]} to {filter_item["end_month"]}]')

                    if "options" in filter_item:
                        option_strs = [f'{opt["name"]}="{opt["string"]}"' for opt in filter_item["options"]]
                        parts.append(f'options=[{", ".join(option_strs)}]')

                    lines.append(f"    - {', '.join(parts)}")
                else:
                    # Regular filter
                    filter_parts = [filter_item["name"]]
                    if "string" in filter_item:
                        filter_parts.append(filter_item["string"])
                    if "domain" in filter_item:
                        filter_parts.append(f'domain="{filter_item["domain"]}"')
                    lines.append(f"    - {', '.join(filter_parts)}")
        sections.append("\n".join(lines))

    # 3. Groupbys (regular and date)
    regular_groupbys = []
    date_groupbys = []

    def is_date_groupby(value):
        if ":" in value:
            return True
        return model_fields.get(value, {}).get("type") in ["date", "datetime"]

    for group in tree.xpath(".//group"):
        for filter_elem in group.xpath(".//filter[@name and not(@invisible='1')]"):
            if filter_elem.get("context") and "group_by" in filter_elem.get("context"):
                context_str = filter_elem.get("context")
                context_dict = literal_eval(context_str)
                raw_group_by = context_dict.get("group_by")
                group_bys = [raw_group_by] if isinstance(raw_group_by, str) else raw_group_by or []

                for group_by in group_bys:
                    groupby_info = {
                        "name": filter_elem.get("name"),
                        "string": filter_elem.get("string") or ""
                    }

                    if is_date_groupby(group_by):
                        field_name, *interval = group_by.split(":", 1)
                        interval = interval[0] if interval else "month"
                        groupby_info["field_name"] = field_name
                        groupby_info["default_interval"] = interval
                        date_groupbys.append(groupby_info)
                    else:
                        groupby_info["field_name"] = group_by
                        regular_groupbys.append(groupby_info)

    if regular_groupbys:
        lines = ["Groupbys:"]
        for groupby in regular_groupbys:
            parts = [groupby["field_name"]]
            if groupby["string"]:
                parts.append(groupby["string"])
            lines.append(f"  - {', '.join(parts)}")
        sections.append("\n".join(lines))

    if date_groupbys:
        lines = ["Date groupbys:"]
        for groupby in date_groupbys:
            parts = [groupby["field_name"]]
            if groupby["string"]:
                parts.append(groupby["string"])
            parts.append(f"default_interval={groupby['default_interval']}")
            lines.append(f"  - {', '.join(parts)}")
        sections.append("\n".join(lines))

    result = "\n\n".join(sections)
    return result


def get_date_filters(search_view_arch):
    """Extract date filter configs from search view: {field_name: {custom_options, start/end ranges}}"""
    if not search_view_arch:
        return {}

    date_filters = {}

    try:
        tree = etree.fromstring(search_view_arch)
        for date_filter in tree.xpath(".//filter[@date and @name and not(@invisible='1')]"):
            field_name = date_filter.get("date")

            # Extract range parameters (defaults from web/static/src/search/search_arch_parser.js)
            config = {
                'custom_options': [],
                'start_year': int(date_filter.get('start_year', -2)),
                'end_year': int(date_filter.get('end_year', 0)),
                'start_month': int(date_filter.get('start_month', -2)),
                'end_month': int(date_filter.get('end_month', 0)),
            }

            # Extract custom options from child <filter> elements if present
            # Prefix with "custom_" to match client-side behavior
            child_filters = date_filter.xpath("./filter[@name]")
            if child_filters:
                config['custom_options'] = [f"custom_{child.get('name')}" for child in child_filters]

            date_filters[field_name] = config
    except etree.XMLSyntaxError:
        # If search view is invalid, return empty dict
        return {}

    return date_filters


def _validate_field_type(model, model_fields, field_name, allowed_types, error_list):
    field_info = model_fields.get(field_name, {})
    if not field_info:
        error_list.append(f"Field '{field_name}' does not exist in model {model._name}")
        return False

    if field_info.get('type') not in allowed_types:
        type_str = '/'.join(allowed_types)
        actual_type = field_info.get('type')
        error_list.append(f"Field '{field_name}' is not a {type_str} field (type: {actual_type})")
        return False

    return True


def validate_measures(model, measures):
    fields = model.fields_get()
    valid_measures_dict = compute_report_measures(fields, None)
    for measure in measures:
        parts = measure.strip().split()
        if ':' in parts[0]:
            raise ValueError(
                f"Invalid measure syntax '{measure}' for model '{model}'. "
                "Aggregation operators like ':sum' are not supported. "
                "Use '<field_name>' or '<field_name> asc/desc' instead."
            )
        base_measure = parts[0]
        if base_measure not in valid_measures_dict:
            raise ValueError(
                f"Measure '{base_measure}' is invalid for model '{model}'. "
                f"The base field is not a recognized or aggregatable field."
            )


def validate_regular_groupbys(model, groupbys):
    if not groupbys:
        return

    model_fields = model.fields_get()
    invalid_groupbys = []
    for groupby in groupbys:
        if len(groupby.split(".")) > 1 or not model_fields.get(groupby, {}).get('groupable'):
            invalid_groupbys.append(groupby)

    if invalid_groupbys:
        raise ValueError(f"The following groupby values are not allowed: {invalid_groupbys}")


def validate_date_groupbys(model, date_groupbys):
    if not date_groupbys:
        return

    model_fields = model.fields_get()
    invalid_date_groupbys = []

    for date_groupby in date_groupbys:
        field_name = date_groupby['field_name']
        intervals = date_groupby['intervals']

        invalid_intervals = [i for i in intervals if i not in VALID_INTERVALS]
        if invalid_intervals:
            invalid_date_groupbys.append(f"Invalid intervals '{invalid_intervals}' for field '{field_name}'. Valid intervals: {VALID_INTERVALS}")
            continue

        if not _validate_field_type(model, model_fields, field_name, ['date', 'datetime'], invalid_date_groupbys):
            continue

    if invalid_date_groupbys:
        raise ValueError(f"Invalid date_groupbys: {'; '.join(invalid_date_groupbys)}")


def validate_groupbys(model, groupbys):
    """Validate a mixed list of string groupbys and date groupby objects."""
    if not groupbys:
        return

    string_groupbys = []
    date_groupbys = []

    for groupby in groupbys:
        if isinstance(groupby, str):
            string_groupbys.append(groupby)
        elif isinstance(groupby, dict):
            date_groupbys.append(groupby)
        else:
            raise TypeError(f"Invalid groupby type for '{groupby}'. Expected string or dict.")

    validate_regular_groupbys(model, string_groupbys)
    validate_date_groupbys(model, date_groupbys)


def validate_date_filters(model, filters, action=None):
    """
    Validate date filter objects in a mixed list of filters.
    Accepts a list containing both regular filter names (strings) and date filter objects (dicts).
    Only validates date filter objects, ignoring string filters.
    """
    if not filters:
        return

    # Get search view architecture from action if provided
    search_view_arch = None
    if action:
        search_view = get_search_view(model, action)
        search_view_arch = search_view.get('arch') if search_view else None

    model_fields = model.fields_get()
    invalid_date_filters = []
    date_filter_configs = get_date_filters(search_view_arch) if search_view_arch else {}

    for filter_item in filters:
        # Skip non-date filters (strings)
        if not isinstance(filter_item, dict):
            continue

        date_filter = filter_item
        field_name = date_filter['field_name']
        selected_periods = date_filter['selected_periods']

        if not _validate_field_type(model, model_fields, field_name, ['date', 'datetime'], invalid_date_filters):
            continue

        # Check if field is available as a date filter in the search view
        if field_name not in date_filter_configs:
            available_filters = list(date_filter_configs.keys()) if date_filter_configs else []
            if available_filters:
                invalid_date_filters.append(
                    f"{field_name} is not available as a date filter in the search view. "
                    f"Available date filters: {', '.join(available_filters)}. "
                    f"For {field_name}, use custom_domain with the 'ai_tool_compute_date' tool to get date/time values."
                )
            else:
                invalid_date_filters.append(
                    f"{field_name} is not available as a date filter in the search view (no date filters available). "
                    f"Use custom_domain with the 'ai_tool_compute_date' tool to get date/time values for {field_name}."
                )
            continue  # Skip to next date_filter

        # Validate each period for this field
        config = date_filter_configs[field_name]
        custom_options = config.get('custom_options', [])
        invalid_periods = []

        for period in selected_periods:
            if period in custom_options:
                continue

            if period in VALID_QUARTERS:
                continue

            # check if a valid period with offset (month+-N, year+-N)
            def check_valid_period(period_type):
                match = re.match(rf'^{period_type}([+-]\d{{1,2}})?$', period)
                if match:
                    offset = int(match.group(1) or 0)
                    start_period = config.get(f'start_{period_type}', -2)
                    end_period = config.get(f'end_{period_type}', 0)
                    if not start_period <= offset <= end_period:
                        invalid_periods.append(f"'{period}' (offset {offset} outside range [{start_period}, {end_period}])")
                    return True
                return False

            if not (check_valid_period('month') or check_valid_period('year')):
                invalid_periods.append(
                    f"'{period}' (not a valid pattern. "
                    f"Valid: month, year (with offsets), quarters (first_quarter, second_quarter, third_quarter, fourth_quarter). "
                    f"Custom options: {custom_options if custom_options else 'none'})",
                )

        if invalid_periods:
            invalid_date_filters.append(f"Invalid period formats for field '{field_name}': {', '.join(invalid_periods)}")

    if invalid_date_filters:
        raise ValueError(f"Invalid date_filters: {'; '.join(invalid_date_filters)}")


def validate_search_terms(search_terms):
    if not search_terms:
        return

    invalid_search_terms = []
    for search_term in search_terms:
        field = search_term["search_field"]
        if "." in field:
            invalid_search_terms.append(search_term)

    if invalid_search_terms:
        raise ValueError(f"Search terms with field chains (containing '.') are not allowed: {invalid_search_terms}")


def compute_date(field_type, user_tz, today, operations=None, pin=None):
    """
    Compute a date/datetime value based on operations and pinning.

    This function allows computing exact date/datetime values for any relative date expression.
    The user thinks in their timezone, and this function handles conversion to UTC transparently.

    Args:
        field_type (str): 'date' or 'datetime' (already validated by caller)
        user_tz (str): Timezone string like 'America/New_York' or 'UTC'
        today (date): Today's date (from fields.Date.context_today, respects test mocking)
        operations (list): Sequential operations to apply (navigate, find_previous, find_next)
        pin (dict): Final anchoring within result (month, day, weekday, weekday_occurrence, time)

    Returns:
        str: Date string in 'YYYY-MM-DD' format for date fields, or
             'YYYY-MM-DD HH:MM:SS' format for datetime fields (in UTC)
    """
    # Start at midnight in user timezone (operations/boundaries/pins will adjust time as needed)
    working_dt = datetime.combine(today, datetime.min.time(), tzinfo=(ZoneInfo(user_tz)))

    for op in operations or []:
        match op["type"]:
            case "navigate":
                working_dt = _compute_date_navigate(working_dt, op)
            case "find_previous":
                working_dt = _compute_date_find_weekday(working_dt, op["weekday"], direction=-1)
            case "find_next":
                working_dt = _compute_date_find_weekday(working_dt, op["weekday"], direction=1)
            case _:
                raise ValueError(f"Unknown operation type: {op['type']}")

    if pin:
        working_dt = _compute_date_apply_pin(working_dt, pin)

    if field_type == "date":
        return working_dt.strftime(DEFAULT_SERVER_DATE_FORMAT)

    working_dt_utc = working_dt.astimezone(UTC)
    return working_dt_utc.strftime(DEFAULT_SERVER_DATETIME_FORMAT)


def _clamp_day_to_month(year, month, day):
    """Clamp a day value to the valid range for the given year and month."""
    max_day = calendar.monthrange(year, month)[1]
    return min(day, max_day)


def _add_months_with_clamping(working_dt, months_offset):
    """
    Add months to a datetime with day clamping.

    Handles month/year overflow and ensures the day is valid for the target month
    (e.g., Jan 31 + 1 month = Feb 28/29, not Feb 31).
    """
    total_months = (working_dt.month - 1) + months_offset  # Convert to 0-indexed
    new_year = working_dt.year + (total_months // 12)
    new_month = (total_months % 12) + 1  # Back to 1-indexed
    new_day = _clamp_day_to_month(new_year, new_month, working_dt.day)
    return working_dt.replace(year=new_year, month=new_month, day=new_day)


def _compute_date_navigate(working_dt, op):
    """Execute a navigate operation on the working datetime."""
    period = op["period"]
    offset = op.get("offset") or 0
    boundary = op.get("boundary")

    if offset < MIN_OFFSET or offset > MAX_OFFSET:
        raise ValueError(f"offset must be between {MIN_OFFSET} and {MAX_OFFSET}")

    match period:
        case "minute":
            result = working_dt + timedelta(minutes=offset)
        case "hour":
            result = working_dt + timedelta(hours=offset)
        case "day":
            result = working_dt + timedelta(days=offset)
        case "week":
            result = working_dt + timedelta(weeks=offset)
        case "month":
            result = _add_months_with_clamping(working_dt, offset)
        case "quarter":
            result = _add_months_with_clamping(working_dt, offset * 3)
        case "year":
            result = _add_months_with_clamping(working_dt, offset * 12)

    # Apply boundary semantics
    if boundary in BOUNDARY_TIME_RESETS:
        time_resets = BOUNDARY_TIME_RESETS[boundary]

        match period:
            case "minute" | "hour" | "day":
                result = result.replace(**time_resets[period])
            case "week":
                # Start of week (Monday): negative offset, End of week (Sunday): positive offset
                days_offset = -result.weekday() if boundary == "start" else 6 - result.weekday()
                result = result + timedelta(days=days_offset)
                result = result.replace(**time_resets['day'])
            case "month":
                day = 1 if boundary == "start" else calendar.monthrange(result.year, result.month)[1]
                result = result.replace(day=day, **time_resets['day'])
            case "quarter":
                quarter = (result.month - 1) // 3 + 1
                month = QUARTER_MONTHS[quarter][0 if boundary == "start" else -1]
                day = 1 if boundary == "start" else calendar.monthrange(result.year, month)[1]
                result = result.replace(month=month, day=day, **time_resets['day'])
            case "year":
                month = 1 if boundary == "start" else 12
                day = 1 if boundary == "start" else 31
                result = result.replace(month=month, day=day, **time_resets['day'])

    return result


def _compute_date_find_weekday(working_dt, target_weekday, direction):
    """
    Helper function to find a specific weekday occurrence.

    Args:
        working_dt: Current datetime to search from
        target_weekday: Target weekday (0=Monday, 6=Sunday)
        direction: 1 for next, -1 for previous

    Returns:
        Datetime of the target weekday occurrence
    """
    if target_weekday < 0 or target_weekday > 6:
        raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")

    current_weekday = working_dt.weekday()
    days_offset = (direction * (target_weekday - current_weekday)) % 7 or 7
    result = working_dt + timedelta(days=days_offset * direction)
    return result


def _compute_date_apply_pin(working_dt, pin):
    """Apply pin logic to anchor the working datetime to a specific position.

    Pin structure:
    - pin.day as int: day of month (1-31)
    - pin.day as object: {weekday: int, occurrence?: int}
    - pin.time: string in HH:MM or HH:MM:SS format
    """
    result = working_dt

    # Apply day pin
    if "day" in pin and pin["day"] is not None:
        day_value = pin["day"]

        if isinstance(day_value, int):
            # Simple day of month
            if not (1 <= day_value <= 31):
                raise ValueError("pin.day must be between 1 and 31")

            day = day_value
            max_day = calendar.monthrange(result.year, result.month)[1]
            if not (1 <= day <= max_day):
                raise ValueError(
                    f"pin.day must be between 1 and {max_day} for {result.year}-{result.month:02d}",
                )
            result = result.replace(day=day)

        elif isinstance(day_value, dict):
            # Weekday selector: {weekday: int, occurrence?: int}
            if "weekday" not in day_value:
                raise ValueError(
                    f"pin.day object must have 'weekday' field. Got: {day_value}"
                )

            target_weekday = day_value["weekday"]
            if not isinstance(target_weekday, int):
                raise TypeError("pin.day.weekday must be an integer (0=Monday, 6=Sunday)")
            if not (0 <= target_weekday <= 6):
                raise ValueError("pin.day.weekday must be between 0 (Monday) and 6 (Sunday)")

            if "occurrence" in day_value and day_value["occurrence"] is not None:
                occurrence = day_value["occurrence"]
                if not isinstance(occurrence, int):
                    raise ValueError("pin.day.occurrence must be an integer")
                if not (1 <= occurrence <= 5):
                    raise ValueError("pin.day.occurrence must be between 1 and 5")

                first_of_month = result.replace(day=1)
                first_weekday = first_of_month.weekday()
                days_to_first = (target_weekday - first_weekday) % 7
                first_occurrence = first_of_month + timedelta(days=days_to_first)
                target_day = first_occurrence + timedelta(weeks=occurrence - 1)

                if target_day.month != result.month:
                    raise ValueError(
                        f"The {occurrence}th occurrence of weekday {target_weekday} does not exist in month {result.month}",
                    )

                result = result.replace(day=target_day.day)
            else:
                # Just find the weekday without occurrence
                current_weekday = result.weekday()
                days_diff = target_weekday - current_weekday
                result = result + timedelta(days=days_diff)
        else:
            raise ValueError("pin.day must be an integer (1-31) or object {weekday, occurrence?}")

    # Apply time pin
    if "time" in pin and pin["time"] is not None:
        time_str = pin["time"]
        if not isinstance(time_str, str):
            raise ValueError("pin.time must be a string in 'HH:MM' or 'HH:MM:SS' format")

        time_parts = time_str.split(":")
        if len(time_parts) not in [2, 3]:
            raise ValueError("pin.time must be in 'HH:MM' or 'HH:MM:SS' format")

        try:
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) == 3 else 0
        except ValueError:
            raise ValueError("pin.time components must be integers") from None

        if not (0 <= hour <= 23):
            raise ValueError("pin.time hour must be between 0 and 23")
        if not (0 <= minute <= 59):
            raise ValueError("pin.time minute must be between 0 and 59")
        if not (0 <= second <= 59):
            raise ValueError("pin.time second must be between 0 and 59")

        result = result.replace(hour=hour, minute=minute, second=second, microsecond=0)

    return result


def markdown_format(text):
    if CustomMarkdown:
        raw_html = CustomMarkdown(
            extras=['fenced-code-blocks', 'tables', 'strike', 'cuddled-lists', 'highlightjs-lang', 'break-on-newline']
        ).convert(text).strip()
        text = format_html_response(raw_html)
    return html_sanitize(text, sanitize_attributes=True, sanitize_style=True)


def format_html_response(html_string):
    if not html_string:
        return
    html_tree = html.fromstring(html_string)
    class_map = {
        "table": "table o_table table-light table-hover o-scrollbar-thin table-bordered ai-table-response my-2",
        "thead": "table-secondary",
        "pre": "ai-pre-response o-scrollbar-thin",
        "code": "ai-code-response",
    }
    for element in html_tree.xpath("//table | //thead | //pre | //code"):
        element.attrib["class"] = f'{element.attrib.get("class", "")} {class_map[element.tag]}'

    # If the root element is a div and the original string did not start with a div,
    # it means lxml.html.fromstring added an implicit wrapper. We unwrap it.
    if html_tree.tag == 'div' and not html_string.strip().lower().startswith('<div'):
        return ''.join(html.tostring(child, encoding='unicode', method='html') for child in html_tree.iterchildren())
    return html.tostring(html_tree, encoding='unicode', method='html')


def make_confirmation_request_preview(env, body):
    return {
        'type': 'confirmation',
        'body': body,
        'choices': [
            {'label': env._("Yes, do it"), 'value': UserInputResponse.CONFIRM_ONCE},
            {'label': env._("Yes, always approve in this chat"), 'value': UserInputResponse.AUTO_CONFIRM},
            {'label': env._("No, I want something else"), 'value': UserInputResponse.DECLINE},
        ],
        'allow_free_text': False,
    }


def make_records_update_preview(records, changes):
    env = records.env
    fnames = changes.keys()
    new_rec = records[0].new(changes, origin=records[0])
    new_vals = new_rec.read(fnames)[0]
    old_vals = records.read(fnames)[0]

    items = []
    for fname in fnames:
        field = records._fields[fname]
        if field.readonly:
            raise ValueError(f"Field {fname} is readonly and cannot be updated. Try to update another field")
        if field.type in ('binary', 'image', 'properties'):
            raise ValueError(f"Field of type {field.type} cannot be updated ({fname})")
        if field.type in ('many2many', 'one2many'):
            if not isinstance(changes[fname], list) or not isinstance(changes[fname][0], tuple):
                raise ValueError(f"{fname} is a x2many and expects a Command as value. Try again with a Command")
            cmd_items = []
            comodel = _get_comodel(env, field)
            for cmd in changes[fname]:
                if cmd[0] in (Command.CREATE, Command.UPDATE, Command.DELETE):
                    raise ValueError(f"Command {cmd[0]} cannot be used during an update.")
                if cmd[0] == Command.UNLINK:
                    cmd_items.append(env._(
                        'Remove "%(record_name)s"',
                        record_name=Markup("<i>%s</i>") % comodel.browse(cmd[1]).display_name,
                    ))
                elif cmd[0] == Command.LINK:
                    cmd_items.append(env._(
                        'Add "%(record_name)s"',
                        record_name=Markup("<i>%s</i>") % comodel.browse(cmd[1]).display_name,
                    ))
                elif cmd[0] == Command.CLEAR:
                    cmd_items.append(env._("Remove all"))
                elif cmd[0] == Command.SET:
                    cmd_items.append(env._(
                        "Replace all by %(new_relations)s",
                        new_relations=Markup("<ul>%s</ul>") % Markup().join(
                            Markup("<li>%s</li>") % rec.display_name
                            for rec in comodel.browse(cmd[2])
                        )
                    ))
            if len(cmd_items) > 1:
                val = Markup("<ul>%s</ul>") % Markup().join(Markup("<li>%s</li>") % i for i in cmd_items)
            elif cmd_items:
                val = cmd_items[0]
            else:
                val = ""
        elif field.type in ('html', 'text'):
            if field.type == "html":
                old_vals[fname] = html_to_inner_content(old_vals[fname])
                new_vals[fname] = html_to_inner_content(new_vals[fname])
            # only crop the previous val as the user needs to see the whole new value to approve it
            if old_vals[fname] and len(old_vals[fname]) > 120:
                old_vals[fname] = old_vals[fname][:50] + "..." + old_vals[fname][-50:]
            val = new_vals[fname]
        elif field.type == 'many2one':
            old_vals[fname] = records[0][fname].display_name
            val = new_rec[fname].display_name
        elif field.type == 'date':
            old_vals[fname] = format_date(env, old_vals[fname])
            val = format_date(env, new_vals[fname])
        elif field.type == 'datetime':
            old_vals[fname] = format_datetime(env, old_vals[fname])
            val = format_datetime(env, new_vals[fname])
        elif field.type == 'selection':
            old_vals[fname] = field._selection.get(old_vals[fname])
            val = field._selection.get(new_vals[fname])
        else:
            val = new_vals[fname]

        item = {
            'field_name': field.string,
            'new_val': val if val not in (False, None) else env._("None"),
        }
        if not (
            field.type in ('one2many', 'many2many') or
            len(records) > 1 and len(records.mapped(fname)) > 1 or
            fname == records._rec_name
        ):
            item['old_val'] = old_vals[fname] if old_vals[fname] not in (False, None) else env._("None")
        items.append(item)
    return items


def make_batch_update_preview(env, explanation, updates):
    if len(updates) > 50:
        raise ValueError("Max 50 updates at a time are authorized")

    def _get_update_preview(update):
        model_name = update['model_name']
        domain = update['domain']
        changes_data = update['changes']
        changes = {c['field']: ast.literal_eval(c['x2m_commands']) if c.get('x2m_commands') else c.get('value') for c in changes_data}

        if (model := env.get(model_name)) is None:
            raise ValueError(f"Model {model_name} does not exists")

        # sudo(False) just in case the tool ever gets run in a sudo-ed env (shouldn't happen)
        model = model.sudo(False)
        parsed_domain = env['ai.tool']._parse_domain(model_name, domain, operation='write')
        if parsed_domain in (True, []):
            raise ValueError("You cannot update using a dummy truthy domain (e.g. [], True). To update all records, pass a domain that matches all records instead.")
        records = model.search(parsed_domain)
        records.check_access('write')

        if not records:
            return None

        if len(records) == 1:
            if records._name == env.context.get('active_model') and records.id == env.context.get('active_id'):
                label = env._("Current record")
            else:
                label = Markup('%s "%s"') % (records._description, Markup("<i>%s</i>") % records.display_name)
        else:
            label = env._("%(nb_records)s records (%(record_model)s)",
                nb_records=len(records),
                record_model=records._description
            )

        return {
            'label': label,
            'items': make_records_update_preview(records, changes),
        }

    sections = [p for u in updates if (p := _get_update_preview(u))]
    if not sections:
        raise ValueError("No records matched the given domain. Try again with another domain")

    return env['ir.qweb']._render('ai.ai_records_preview', {"template": "update", "explanation": explanation, 'sections': sections})


def make_create_preview(env: Environment, explanation: str, model_name: str, preview_data: list[dict]):
    def _get_create_preview(record_info: dict):
        field_values_data = record_info["field_values"]
        vals = {
            c["field"]: c.get("x2m_link_ids") if c.get("x2m_link_ids") else c.get("value")
            for c in field_values_data
        }

        model: BaseModel = env.get(model_name)
        model = model.sudo(False)
        if model is None:
            raise ValueError(f"Model {model_name} does not exists")
        model.check_access("create")

        return make_record_create_preview(model, vals)

    preview_per_model = defaultdict(list)
    for record_info in preview_data:
        if p := _get_create_preview(record_info):
            preview_per_model[model_name].append({"label": env.get(model_name)._description, "items": p})

    sections = []
    for model_name, preview_items in preview_per_model.items():
        for index, preview in enumerate(preview_items):
            if len(preview_items) > 1:
                preview["label"] = f"{preview['label']} {index + 1}"
            sections.append(preview)

    return env["ir.qweb"]._render(
        "ai.ai_records_preview",
        {"template": "create", "explanation": explanation, "sections": sections},
    )


def _get_comodel(env, field):
    comodel = env[field.comodel_name]
    if field.comodel_name == "ir.model":
        comodel = comodel.sudo()
    return comodel


def make_record_create_preview(model: BaseModel, vals: dict):
    fields = []
    for key, val in vals.items():
        if not val:
            continue
        field = model._fields[key]
        formatted_value = val
        if field.type == "date":
            formatted_value = format_date(model.env, val)
        elif field.type == "datetime":
            formatted_value = format_datetime(model.env, val)
        elif field.type in ["html", "text"]:
            formatted_value = val
            if field.type == "html":
                formatted_value = html_to_inner_content(val)
            if formatted_value and len(formatted_value) > 120:
                formatted_value = formatted_value[:50] + "..." + formatted_value[-50:]
        elif field.type == "one2many":
            comodel = _get_comodel(model.env, field)
            cmd_items = []
            index = 1

            def get_label(i: int) -> Markup:
                return Markup("<b>%s %d</b>") % (comodel._description, i)

            if isinstance(val, int):
                cmd_items.append(
                    {
                        "label": get_label(index),
                        "value": Markup('<i>"%s"</i> (existing)') % comodel.browse(val).display_name,
                    }
                )
            elif isinstance(val, list):
                for record in comodel.browse(val):
                    cmd_items.append(
                        {
                            "label": get_label(index),
                            "value": Markup('<i>"%s"</i> (existing)') % record.display_name,
                        }
                    )
                    index += 1
            index += 1
            formatted_value = cmd_items
        elif field.type == "many2many":
            comodel = _get_comodel(model.env, field)
            cmd_items = []
            link_cmd_items: list[str] = []
            if isinstance(val, int):
                link_cmd_items.append(
                    Markup("<i>%s</i>")
                    % comodel.browse(val).display_name,
                )
            elif isinstance(val, list):
                for record in comodel.browse(val):
                    link_cmd_items.append(Markup("<i>%s</i>") % record.display_name)
            if link_cmd_items:
                cmd_items.append({"label": model.env._("Add"), "value": Markup(", ").join(link_cmd_items)})
            formatted_value = cmd_items
        elif field.type == "many2one":
            comodel = _get_comodel(model.env, field)
            formatted_value = comodel.browse(val).display_name
        fields.append({"label": field.string, "value": formatted_value})
    return fields


def is_ai_parts(obj: Any) -> bool:
    if not isinstance(obj, list):
        return False
    for part in obj:
        if not isinstance(part, dict):
            return False
        if part.get('type') not in ('text', 'inline_data'):
            return False
        if part['type'] == 'text' and 'text' not in part:
            return False
        if part['type'] == 'inline_data' and ('mimetype' not in part or 'data' not in part):
            return False
    return True


def format_tool_result(tool_call, result=None, error=None):
    if not is_ai_parts(result):
        if error is not None:
            text = f"Error: {error}"
        elif result is None:
            text = 'success'
        elif not isinstance(result, str):
            text = json.dumps(result, default=json_default, ensure_ascii=False)
        else:
            text = result
        result = [{
            'type': 'text',
            'text': text,
        }]
    return {
        'tool_name': tool_call['name'],
        'tool_call_id': tool_call['call_id'],
        'result': result,
        'success': error is None,
    }


def format_tool_summary(summary, tool_call):
    # add call_id if there are args to show, to show caret in ui only if there's st to load
    data_id = ''
    if tool_call['args'].keys() - {'tool_status', '__final_message', 'explanation'}:
        data_id = Markup('data-id="%s"') % tool_call['call_id']
    return Markup('<div class="o-ai-tool-summary" %s><i class="oi oi-fw me-1" data-icon="%s"/>%s</div>') % (
        data_id,
        summary.get('icon', 'build'),
        summary.get('text'),
    )


def get_text_from_parts(parts: AIMessageParts) -> Any:
    """
    Extracts the text from the parts.
    :param parts: AIMessageParts
    :return: - an empty string if no text parts are found
            - the content of the text part if only one text part is found. The content can be a string, a list, a dict or any JSON compatible format.
            - the combined text from the parts if multiple text parts are found. In such case, the combination logic is only defined if all parts are simple strings.
    """
    all_text = [part['text'] for part in parts if part['type'] == 'text']
    return all_text[0] if len(all_text) == 1 else "\n".join(all_text)


def enable_tools(tool_context: dict, tool_ids: list[int]):
    state = tool_context["state"]
    state["available_tools"] = list(dict.fromkeys(state.get("available_tools", []) + tool_ids))


def enable_skills(tool_context: dict, skill_ids: list[int], tool_ids: list[int]):
    state = tool_context["state"]
    state["loaded_skills"] = list(dict.fromkeys(state.get("loaded_skills", []) + skill_ids))
    enable_tools(tool_context, tool_ids)


def disable_skills(state: dict, skill_ids: list[int], tool_ids: list[int] = ()):
    state = dict(state)
    state["loaded_skills"] = [skill for skill in state["loaded_skills"] if skill not in skill_ids]
    state["available_tools"] = [tool for tool in state["available_tools"] if tool not in tool_ids]
    return state


def split_binary_fields(model, fnames):
    """Split the fields to read from the binary ones."""
    read_fnames = []
    binary_fields = {}
    for fname in fnames or model.fields_get(attributes=()):
        field = model._fields.get(fname)
        if isinstance(field, Binary):
            model.check_field_access(field, 'read')
            binary_fields[fname] = field
        else:
            read_fnames.append(fname)
    return read_fnames or ['id'], binary_fields


def add_binary_references(model, vals_list, binary_fields):
    """Add a reference to each unread binary field"""
    records = model.browse([vals['id'] for vals in vals_list])
    attachments = {
        (attachment.res_field, attachment.res_id): attachment
        for attachment in model.env['ir.attachment']._get_field_attachments(
            records, [fname for fname, field in binary_fields.items() if field.attachment]
        )
    }
    for fname, field in binary_fields.items():
        if field.attachment:
            metadata_by_id = {
                record.id: (attachment.name, attachment.mimetype, attachment.file_size)
                for record in records
                if (attachment := attachments.get((fname, record.id)))
            }
        elif field.store or field.related:
            records.fetch([fname])
            metadata_by_id = {
                record.id: (value.filename, value.mimetype, value.size)
                for record in records
                if (value := record[fname])
            }
        else:
            metadata_by_id = dict.fromkeys(records.ids, (None, None, None))

        is_image = isinstance(field, Image)
        for record, vals in zip(records, vals_list):
            if (metadata := metadata_by_id.get(record.id)) is None:
                vals[fname] = False
                continue
            name, mimetype, size = metadata
            reference = {'is_binary': True}
            if size is not None:
                reference['size'] = size
            if name:
                reference['name'] = name
            if mimetype:
                reference['mimetype'] = mimetype
            if is_image:
                reference['image_path'] = field_to_image_path(record, fname)
            vals[fname] = reference


def format_name_to_llm(name: str):
    # Formats a name to be used as a tool name with LLMs.
    # For a server action called "AI: Create Leads", it returns "ai_create_leads"
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:64] or "tool"
