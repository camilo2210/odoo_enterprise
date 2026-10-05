import { t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { mergeClasses } from "@web/core/utils/classname";
import {
    BadgesSelectionField,
    badgesSelectionField,
} from "@web/views/fields/badges_selection/badges_selection_field";
import {
    BaseBadgesField,
    baseBadgesFieldProps,
} from "@web/views/fields/badges_selection/base_badges_field";

export class WarningColorBadgeBase extends BaseBadgesField {
    props = useProps({
        ...baseBadgesFieldProps,
        getBadgeClassNames: t.function().optional(),
    });

    getBadgeClassNames(option = false) {
        const { readonly, colorField, record } = this.props;
        const colorClass = record.data.warning_color_class;
        const base = "badge rounded-pill";

        if (!readonly) {
            return mergeClasses(`btn-sm ${base}`, {
                "active o_badge_border": this.value === option[0],
            });
        }

        const bg = `bg-${colorClass || "secondary"}-subtle`;
        const colorId = record.data[colorField];
        if (colorField && Number.isInteger(colorId)) {
            return `${base} o_badge_color_${colorId} ${bg}`;
        }

        return mergeClasses(bg, { [`btn btn-secondary ${base}`]: this.value });
    }

    get baseBadgeProps() {
        return {
            ...super.baseBadgeProps(),
            getBadgeClassNames: this.getBadgeClassNames.bind(this),
        };
    }
}

export class WarningColorBadge extends BadgesSelectionField {
    static components = {
        BaseBadgesField: WarningColorBadgeBase,
    };
}

export const warning_color_badge = {
    ...badgesSelectionField,
    component: WarningColorBadge,
};

registry.category("fields").add("list.warning_color_badge", warning_color_badge);
