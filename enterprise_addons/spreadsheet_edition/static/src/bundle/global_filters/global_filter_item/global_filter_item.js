import { Component, proxy, t, useProps } from "@odoo/owl";
import { components } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { deepEqual } from "@web/core/utils/objects";
import {
    getDefaultValue,
    getEmptyFilterValue,
    isEmptyFilterValue,
} from "@spreadsheet/global_filters/helpers";
import { GlobalFilterInput } from "../components/global_filter_input/global_filter_input";

const { CogWheelMenu } = components;

export class GlobalFilterItem extends Component {
    static template = "spreadsheet_edition.GlobalFilterItem";
    static components = { GlobalFilterInput, CogWheelMenu };

    props = useProps({
        filter: t.object(),
        onOpenEditor: t.function(),
        onDeleteFilter: t.function(),
        searchableParentRelations: t.object().optional(),
    });

    setup() {
        this.model = this.env.model;
        this.state = proxy({ value: this.initialValue });
    }

    get initialValue() {
        const value = this.model.getters.getGlobalFilterValue(this.props.filter.id);
        return value ? { ...value } : getDefaultValue(this.props.filter.type);
    }

    get hasClearButton() {
        return !isEmptyFilterValue(this.props.filter, this.state.value);
    }

    get cogWheelMenuItems() {
        return [
            {
                name: _t("Edit"),
                icon: "o-spreadsheet-Icon.EDIT",
                execute: () => this.props.onOpenEditor(this.props.filter.id),
                isEnabledOnLockedSheet: true,
            },
            {
                name: _t("Delete"),
                icon: "o-spreadsheet-Icon.TRASH",
                execute: () => this.props.onDeleteFilter(this.props.filter.id),
                isEnabledOnLockedSheet: true,
            },
        ];
    }

    _syncValue() {
        const { filter } = this.props;
        const original = this.model.getters.getGlobalFilterValue(filter.id);
        const normalized = isEmptyFilterValue(filter, this.state.value)
            ? undefined
            : this.state.value;
        if (!deepEqual(original, normalized)) {
            this.model.dispatch("SET_GLOBAL_FILTER_VALUE", {
                id: filter.id,
                value: normalized,
            });
        }
    }

    updateOperator(operator) {
        if (!operator) {
            this.state.value = undefined;
            this._syncValue();
            return;
        }
        const previousValue = this.state.value || {};
        const defaultValue = getEmptyFilterValue(this.props.filter, operator) || {};
        this.state.value = {
            ...defaultValue,
            ...previousValue,
            operator,
        };
        this._syncValue();
    }

    clearFilter() {
        const value = this.state.value;
        if (!value) {
            return;
        }
        const emptyValue = getEmptyFilterValue(this.props.filter, value.operator);
        this.state.value =
            typeof emptyValue === "object"
                ? { ...emptyValue, operator: value.operator }
                : emptyValue;
        this._syncValue();
    }

    setGlobalFilterValue(value) {
        if (value === undefined && this.props.filter.type !== "date") {
            // preserve operator
            this.state.value = {
                ...this.state.value,
                ...getEmptyFilterValue(this.props.filter, this.state.value?.operator),
            };
        } else {
            this.state.value = value;
        }
        this._syncValue();
    }

    getFilterIcon(type) {
        return (
            {
                date: "calendar_today",
                relation: "link",
                text: "text_fields",
                boolean: "toggle_off",
                selection: "arrow_drop_down",
                numeric: "tag",
            }[type] || "filter_alt"
        );
    }

    getFilterIconClass(type) {
        return (
            {
                date: "oi-filled",
                relation: "",
                text: "",
                boolean: "",
                selection: "",
                numeric: "",
            }[type] || "oi-filled"
        );
    }
}
