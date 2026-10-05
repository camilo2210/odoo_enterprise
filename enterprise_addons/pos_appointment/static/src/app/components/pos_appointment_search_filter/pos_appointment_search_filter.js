import { Component, onMounted, proxy } from "@odoo/owl";
import { localization } from "@web/core/l10n/localization";
import { DateTimePickerPopover } from "@web/core/datetime/datetime_picker_popover";
import { usePopover } from "@web/core/popover/popover_hook";
import { Domain } from "@web/core/domain";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { serializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

const { DateTime } = luxon;

// Time range definitions for filtering appointments by period of day
const TIME_RANGES = {
    morning: { startHour: 0, endHour: 11 },
    afternoon: { startHour: 11, endHour: 17 },
    evening: { startHour: 17, endHour: 24 },
};

export class PosAppointmentSearchFilter extends Component {
    static template = "pos_appointment.PosAppointmentSearchFilter";
    static components = { Dropdown, DropdownItem };

    setup() {
        super.setup(...arguments);
        this.popover = usePopover(DateTimePickerPopover, { position: "bottom" });
        this.state = proxy({
            date: DateTime.now(),
            period: "",
        });
        this.model = this.env.model;
        this.localization = localization;
        this.searchModel = this.model.env.searchModel;
        this.ui = useService("ui");

        this.filters = {
            date_filter: {
                name: "date_filter",
                getDescription: (value) =>
                    _t("Start is %s", value.toFormat(this.localization.dateFormat)),
                getTimeLimits: (value) => ({
                    start: value.set({ hour: 0, minute: 0, second: 0 }),
                    end: value.set({ hour: 23, minute: 59, second: 59 }),
                }),
            },
            hour_filter: {
                name: "hour_filter",
                getDescription: (value) =>
                    _t("Hour is %s", value.charAt(0).toUpperCase() + value.slice(1)),
                getTimeLimits: (value) => {
                    const { startHour, endHour } = TIME_RANGES[value];
                    const date = this.state.date || DateTime.now();
                    return {
                        start: date.set({ hour: startHour, minute: 0, second: 0 }),
                        end: date.set({ hour: endHour - 1, minute: 59, second: 59 }),
                    };
                },
            },
        };
        onMounted(() => {
            this._initializeDateFilter();
            this._initializeHourFilter();
        });
    }

    _initializeDateFilter() {
        const dateFilter = this._findSearchItem("date_filter");
        if (!dateFilter?.id) {
            this._applyFilter("date_filter", this.state.date);
        }
    }

    _initializeHourFilter() {
        const hourFilter = this._findSearchItem("hour_filter");
        if (!hourFilter?.id) {
            const currentHour = DateTime.now().hour;
            const period =
                currentHour < 11 ? "morning" : currentHour < 17 ? "afternoon" : "evening";
            this._applyFilter("hour_filter", period);
        } else {
            this.state.period = hourFilter.description.split(" ").at(-1);
        }
    }

    /**
     * Find a search item by name
     */
    _findSearchItem(name) {
        return Object.values(this.searchModel.searchItems).find((item) => item.name === name);
    }

    _applyFilter(filterName, value) {
        const filter = this.filters[filterName];
        if (!filter) {
            return;
        }

        const { getDescription, getTimeLimits } = this.filters[filterName];
        const { start, end } = getTimeLimits(value);
        if (filterName === "hour_filter") {
            const formatedPeriod = value.charAt(0).toUpperCase() + value.slice(1);
            this.state.period = formatedPeriod;
        }
        const domain = new Domain([
            ["start", ">=", serializeDateTime(start)],
            ["start", "<=", serializeDateTime(end)],
        ]);

        this._updateOrCreateFilter(filterName, domain, getDescription(value));
    }

    _updateOrCreateFilter(name, domain, description) {
        const existingFilter = this._findSearchItem(name);
        if (existingFilter) {
            existingFilter.domain = domain.toString();
            existingFilter.description = description;
            this.searchModel._notify();
            if (!this.searchModel.query.some((q) => q.searchItemId === existingFilter.id)) {
                this.searchModel.toggleSearchItem(existingFilter.id);
            }
        } else {
            this.searchModel.createNewFilters([
                {
                    description,
                    domain: domain.toString(),
                    invisible: "True",
                    type: "filter",
                    name,
                },
            ]);
        }
    }

    onClickDateBtn(ev) {
        this.popover.open(ev.currentTarget, {
            pickerProps: {
                onSelect: async (value) => {
                    if (value) {
                        this.state.date = value;
                        this._applyFilter("date_filter", value);
                        const hourFilter = this._findSearchItem("hour_filter");
                        if (hourFilter && this.state.period) {
                            this.onClickHourFilter(this.state.period.toLowerCase());
                        }
                    } else {
                        this.onRemove(null, "date");
                    }
                    this.popover.close();
                },
                type: "date",
                value: this.state.date,
            },
        });
    }

    /**
     * Remove an active filter
     */
    onRemove(ev, filterType) {
        if (ev) {
            ev.stopPropagation();
        }
        const filterName = filterType === "date" ? "date_filter" : "hour_filter";
        const filter = this._findSearchItem(filterName);
        if (filter && this.searchModel.query.some((q) => q.searchItemId === filter.id)) {
            this.searchModel.toggleSearchItem(filter.id);
        }
        if (filterType === "date") {
            this.state.date = null;
        } else {
            this.state.period = "";
        }
    }

    /**
     * Handle hour filter selection
     */
    onClickHourFilter(period) {
        this._applyFilter("hour_filter", period);
    }
}
