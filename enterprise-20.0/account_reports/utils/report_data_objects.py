import logging
from dataclasses import dataclass, field
from typing import Any, Self

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AccountReportDataCommon:
    """
    Base class for all account report data classes.
    These child classes are used to replace dictionaries in reports such as lines, columns, chatter data, and formatting parameters.
    """

    def __getitem__(self, key):
        """
        __getitem__ is slow and should be avoided at all costs whenever possible
        """
        if key in self.__dataclass_fields__:
            _logger.warning("Use of slow __getitem__ on report data object to get key '%s'. Rather access the attribute directly.", key)
            return getattr(self, key)

    def __setitem__(self, key, value):
        """
        __setitem__ is slow and should be avoided at all costs whenever possible
        """
        if key in self.__dataclass_fields__:
            _logger.warning("Use of slow __setitem__ on report data object to set key '%s'. Rather access the attribute directly.", key)
            return setattr(self, key, value)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        kwargs = {}
        for k, v in (d or {}).items():
            kwargs[k] = v
        return cls(**kwargs)

    def as_dict(self) -> dict[str, Any]:
        result = {}
        for f in self.__dataclass_fields__:
            value = getattr(self, f)
            if value is None:
                continue
            if isinstance(value, AccountReportDataCommon):
                result[f] = value.as_dict()
            elif isinstance(value, list):
                result[f] = [list_val.as_dict() if isinstance(list_val, AccountReportDataCommon) else list_val for list_val in value]
            elif isinstance(value, dict):
                result[f] = {
                    key: (dict_val.as_dict() if isinstance(dict_val, AccountReportDataCommon) else dict_val)
                    for key, dict_val in value.items()
                }
            else:
                result[f] = value
        return result

    def copy(self) -> Self:
        return self.from_dict(self.as_dict())

    def update_values(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if key in self.__dataclass_fields__:
                setattr(self, key, value)


@dataclass(slots=True)
class AccountReportLineChatterData(AccountReportDataCommon):
    model: str | None = None
    id: int | None = None


@dataclass(slots=True)
class AccountReportColumnFormatParamsData(AccountReportDataCommon):
    currency_id: int | None = None
    digits: int | None = None


@dataclass(slots=True)
class AccountReportColumnData(AccountReportDataCommon):
    auditable: bool | None = None
    blank_if_zero: bool | None = None
    cell_label: str | None = None
    column_group_index: int | None = None
    comparison_mode: str | None = None
    css_class: str | None = None
    currency: Any | None = None
    currency_symbol: str | None = None
    digits: int | None = None
    edit_popup_data: Any | None = None
    expression_label: str | None = None
    figure_type: str = 'string'
    format_params: AccountReportColumnFormatParamsData | None = None
    green_on_positive: bool | None = None
    has_sublines: bool | None = None
    info_popup_data: Any | None = None
    is_zero: bool | None = None
    name: str | None = None
    no_format: Any | None = None
    report_line_id: int | None = None
    sortable: bool | None = None

    def __post_init__(self) -> None:
        if self.name is None and self.is_zero is None:
            self.is_zero = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AccountReportColumnData":
        data = dict(d or {})
        if isinstance(data.get("format_params"), dict):
            data["format_params"] = AccountReportColumnFormatParamsData.from_dict(data["format_params"])
        return super(AccountReportColumnData, cls).from_dict(data)


@dataclass(slots=True)
class AccountReportLineData(AccountReportDataCommon):
    account_status: Any | None = None
    annotations: Any | None = None
    action_id: int | None = None
    caret_options: str | None = None
    chatter: AccountReportLineChatterData | None = None
    css_class: str | None = None
    code: str | None = None
    columns: list[AccountReportColumnData] = field(default_factory=list)
    column_percent_comparison_data: AccountReportColumnData | None = None
    debug_popup_data: Any | None = None
    expand_function: str | None = None
    groupby: str | None = None
    horizontal_group_total_data: AccountReportColumnData | None = None
    horizontal_split_side: Any | None = None
    id: Any | None = None
    is_draft: bool | None = None
    level: int | None = None
    name: str | None = None
    offset: Any | None = None
    page_break: Any | None = None
    parent_id: Any | None = None
    unfoldable: bool | None = None
    unfolded: bool | None = None

    custom: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AccountReportLineData":
        data = dict(d or {})
        if isinstance(data.get('columns'), list):
            data['columns'] = [AccountReportColumnData.from_dict(c) for c in data['columns']]
        if isinstance(data.get('column_percent_comparison_data'), dict):
            data['column_percent_comparison_data'] = AccountReportColumnData.from_dict(data['column_percent_comparison_data'])
        if isinstance(data.get('horizontal_group_total_data'), dict):
            data['horizontal_group_total_data'] = AccountReportColumnData.from_dict(data['horizontal_group_total_data'])
        if isinstance(data.get('chatter'), dict):
            data['chatter'] = AccountReportLineChatterData.from_dict(data['chatter'])

        data['custom'] = {k: v for k, v in data.items() if k not in cls.__dataclass_fields__}
        if len(data['custom']) > 0:
            for k in data['custom']:
                data.pop(k)
        else:
            data.pop('custom')

        return super(AccountReportLineData, cls).from_dict(data)

    def as_dict(self) -> dict[str, Any]:
        result_dict = super(AccountReportLineData, self).as_dict()
        custom = result_dict.pop("custom", None) or {}
        result_dict.update(custom)
        return result_dict

    def update_values(self, **kwargs) -> None:
        custom = {k: v for k, v in kwargs.items() if k not in self.__dataclass_fields__}
        self.get_custom().update(custom)
        super(AccountReportLineData, self).update_values(**kwargs)

    def get_custom(self) -> dict[str, Any]:
        if self.custom is None:
            self.custom = dict()

        return self.custom
