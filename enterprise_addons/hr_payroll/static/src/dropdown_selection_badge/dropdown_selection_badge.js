import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { Component, onWillStart, t, useProps } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { cookie } from "@web/core/browser/cookie";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { exprToBoolean } from "@web/core/utils/strings";

export class DropdownSelectionBadge extends Component {
    static template = "hr_payroll.DropdownSelectionBadge";
    props = useProps({
        ...standardFieldProps,
        options: t.object().optional(),
        showSelectedIcon: t.string().optional(),
        highlightChatter: t.boolean().optional(),
        forceReadonly: t.boolean().optional(),
    });

    setup() {
        onWillStart(async () => {
            this.editableOptions = await this.getEditableOptions();
        });
    }

    static components = {
        Dropdown,
        DropdownItem,
    };

    get options() {
        const result = this.props.record.fields[this.props.name].selection
        result.forEach(item => {
            const text = this.props.options[item[0]]?.text 
            if (text) {
                item[1] = _t(text)
            }
        })
        return result;
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    get required() {
        return this.props.record.fields[this.props.name].required;
    }

    get display() {
        const result = this.options.filter((val) => val[0] === this.value)[0];
        if(result) {
            return this.props.options[result[0]].text ? this.props.options[result[0]].text : result[1];
        }
        return null;
    }

    get showIcon() {
        const result = this.options.filter((val) => val[0] === this.value)[0];
        return this.props.showSelectedIcon && result
    }

    async getEditableOptions() {
        const editableOptions = [];
        if (this.props.options[false] === undefined) {
            editableOptions.push(false);
        }

        for (const [key, value] of Object.entries(this.props.options)) {
            if (
                [true, undefined].includes(value.can_edit)
                || (typeof value.can_edit === 'string' && (await Promise.all(
                    value.can_edit.split(",").map(group => user.hasGroup(group)),
                )).some(Boolean))
            ) {
                editableOptions.push(key === 'false' ? false : key);
            }
        }

        return editableOptions;
    }

    get canEditAny() {
        return !this.props.forceReadonly && this.editableOptions.length > 0;
    }

    getDropdownButtonDecoration(value) {
        const decoration = this.props.options[value]?.decoration;
        if (!decoration || decoration === 'muted') {
            return 'btn-outline-secondary';
        }
        return `btn-outline-${decoration}`;
    }

    getDropdownItemDecoration(value) {
        const colorScheme = cookie.get("color_scheme");
        const decoration = this.props.options[value]?.decoration;
        const icon = this.props.options[value]?.icon;
        const decorationClassName = icon ? 'text' : 'text-bg';
        if (decoration) {
            if (decoration === "muted") {
                return colorScheme === 'dark' ? "text-200" : "text-300";
            }
            return `${decorationClassName}-${decoration}`;
        }
        return `${decorationClassName}-200`;
    }

    getIcon(value) {
        return this.props.options[value]?.icon || "circle";
    }

    getIconClass(value) {
        return this.props.options[value]?.iconClass || "oi-filled";
    }

    get additionalClassName() {
        return this.props.class || "";
    }

    async onChange(value) {
        await this.props.record.update(
            { [this.props.name]: value },
            { save: true },
        );
    }

    onBadgeHover() {
        if (!this.props.highlightChatter) {
            return;
        }
        const dateToReview = this.props.record.data.date_to_review;
        if (!dateToReview) {
            return;
        }
        const model = this.props.record.resModel;
        const id = this.props.record.resId;
        if (!model || !id) {
            return;
        }
        this.env.bus.trigger("HR_PAYROLL:HIGHLIGHT_MESSAGES", {
            threadModel: model,
            threadId: id,
            dateToReview: dateToReview,
        });
    }

    onBadgeLeave() {
        if (!this.props.highlightChatter) {
            return;
        }
        const model = this.props.record.resModel;
        const id = this.props.record.resId;
        if (!model || !id) {
            return;
        }
        this.env.bus.trigger("HR_PAYROLL:CLEAR_HIGHLIGHTS", {
            threadModel: model,
            threadId: id,
        });
    }
}

export const dropdownSelectionBadge = {
    supportedTypes: ["selection"],
    component: DropdownSelectionBadge,
    extractProps: ({ attrs, options }) => {
        return {
            options,
            showSelectedIcon: attrs.icon,
            highlightChatter: attrs.highlight_chatter === "1",
            forceReadonly: exprToBoolean(attrs.readonly),
        };
    },
};

registry.category("fields").add("dropdown_selection_badge", dropdownSelectionBadge);
