import {
    ModelFieldSelectorPopover,
    modelFieldSelectorPopoverProps,
} from "@web/core/model_field_selector/model_field_selector_popover";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";

import { _t } from "@web/core/l10n/translation";
import { useProps, t } from "@odoo/owl";

/**
 * This override prevents following relations for many2many fields.
 */
export class SidepanelModelFieldSelectorPopover extends ModelFieldSelectorPopover {
    static template = "spreadsheet_edition.SidepanelModelFieldSelectorPopover";

    props = useProps({
        ...modelFieldSelectorPopoverProps,
        canFollowComputedRelation: t.boolean().optional(),
    });

    canFollowRelationFor(fieldDef) {
        if (fieldDef.type === "many2many") {
            return false;
        }
        if (!this.props.canFollowComputedRelation && !fieldDef.store) {
            return false;
        }
        return super.canFollowRelationFor(fieldDef);
    }

    duplicateTooltip(alreadyPresent) {
        return alreadyPresent ? _t("Already present in the source") : undefined;
    }

    filter(fieldDefs, path, resModel) {
        const result = {};
        for (const key in fieldDefs) {
            const field = fieldDefs[key];
            const filterResult = this.props.filter(field, path, resModel);
            if (!filterResult) {
                continue;
            }
            if (typeof filterResult === "object") {
                result[key] = { ...field, ...filterResult };
            } else {
                result[key] = field;
            }
        }
        return result;
    }
}

export class SidepanelModelFieldSelector extends ModelFieldSelector {
    static template = "spreadsheet_edition.SidepanelModelFieldSelector";
    static components = {
        Popover: SidepanelModelFieldSelectorPopover,
    };
    // Inline copy of ModelFieldSelector's props schema (no exported const upstream)
    props = useProps({
        resModel: t.string(),
        path: t.any().optional(),
        allowEmpty: t.boolean().optional(false),
        readonly: t.boolean().optional(true),
        readProperty: t.boolean().optional(),
        showSearchInput: t.boolean().optional(true),
        isDebugMode: t.boolean().optional(false),
        update: t.function().optional(() => () => {}),
        filter: t.function().optional(),
        sort: t.function().optional(),
        followRelation: t.or([t.boolean(), t.function()]).optional(true),
        showDebugInput: t.boolean().optional(),
        canFollowComputedRelation: t.boolean().optional(),
        slots: t.object().optional(),
    });

    getPopoverProps() {
        return {
            ...super.getPopoverProps(),
            canFollowComputedRelation: this.props.canFollowComputedRelation,
            slots: this.props.slots,
        };
    }
}

export class InlineModelFieldSelector extends SidepanelModelFieldSelector {
    static template = "web._ModelFieldSelector";
}
