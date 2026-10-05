import { CheckboxItem } from "@web/core/dropdown/checkbox_item";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, t, useProps } from "@odoo/owl";

const SELECTOR_VALUES = {
    month_days: {
        labels: Array.from({ length: 31 }, (_, index) => String(index + 1)),
        readonlyLabel: _t("Any day"),
    },
    months: {
        labels: [
            _t("January"),
            _t("February"),
            _t("March"),
            _t("April"),
            _t("May"),
            _t("June"),
            _t("July"),
            _t("August"),
            _t("September"),
            _t("October"),
            _t("November"),
            _t("December"),
        ],
        readonlyLabel: _t("Any month"),
    },
    week_days: {
        labels: [
            _t("Monday"),
            _t("Tuesday"),
            _t("Wednesday"),
            _t("Thursday"),
            _t("Friday"),
            _t("Saturday"),
            _t("Sunday"),
        ],
        readonlyLabel: _t("Any day"),
    },
};

export function parseRanges(value, maximum) {
    const selectedValues = new Set();
    for (const item of (value || "").split(",")) {
        const [start, end = start] = item.trim().split("-", 2).map(Number);
        if (start >= 1 && start <= end && end <= maximum) {
            for (let value = start; value <= end; value++) {
                selectedValues.add(value);
            }
        }
    }
    return selectedValues;
}

export function formatRanges(selectedValues) {
    const values = [...selectedValues].sort((a, b) => a - b);
    const ranges = [];
    for (const value of values) {
        const lastRange = ranges.at(-1);
        if (lastRange && value === lastRange[1] + 1) {
            lastRange[1] = value;
        } else {
            ranges.push([value, value]);
        }
    }
    return ranges.map(([start, end]) => (start === end ? `${start}` : `${start}-${end}`)).join(",");
}

export class TimeConditionPeriodAutocomplete extends Component {
    static components = { CheckboxItem, Dropdown };
    static template = "voip.TimeConditionPeriodAutocomplete";

    props = useProps({
        ...standardFieldProps,
        selector: t.string(),
    });

    get config() {
        return SELECTOR_VALUES[this.props.selector];
    }

    get selectedValues() {
        return parseRanges(this.props.record.data[this.props.name], this.config.labels.length);
    }

    get readonlyValue() {
        if (this.isAllSelected) {
            return this.config.readonlyLabel;
        }
        return [...this.selectedValues].map((value) => this.config.labels[value - 1]).join(", ");
    }

    get displayValue() {
        if (this.isAllSelected) {
            return this.config.readonlyLabel;
        }
        if (this.isEmpty) {
            return _t("None");
        }
        if (this.selectedValues.size <= 3) {
            return this.readonlyValue;
        }
        return _t("%s selected", this.selectedValues.size);
    }

    get isAllSelected() {
        return this.selectedValues.size === this.config.labels.length;
    }

    get isEmpty() {
        return this.selectedValues.size === 0;
    }

    get options() {
        return this.config.labels.map((label, index) => ({
            checked: this.selectedValues.has(index + 1),
            label,
            value: index + 1,
        }));
    }

    toggle(value) {
        const selectedValues = this.selectedValues;
        if (selectedValues.has(value)) {
            selectedValues.delete(value);
        } else {
            selectedValues.add(value);
        }
        this.update(selectedValues);
    }

    selectAll() {
        this.update(new Set(this.config.labels.map((label, index) => index + 1)));
    }

    clearAll() {
        this.update(new Set());
    }

    update(selectedValues) {
        this.props.record.update({ [this.props.name]: formatRanges(selectedValues) });
    }
}

registry.category("fields").add("voip_time_condition_period_autocomplete", {
    component: TimeConditionPeriodAutocomplete,
    displayName: _t("Time Condition period autocomplete"),
    supportedTypes: ["char"],
    extractProps: ({ options }) => ({
        selector: options.selector,
    }),
});
