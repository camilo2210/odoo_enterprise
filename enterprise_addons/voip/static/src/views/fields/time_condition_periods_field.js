import { makeContext } from "@web/core/context";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

export class TimeConditionPeriodsField extends X2ManyField {
    async onAdd({ context, editable } = {}) {
        const creationContext = makeContext([this.props.context, context]);
        if (editable || !creationContext.default_mode) {
            return super.onAdd({ context, editable });
        }
        const title =
            creationContext.default_mode === "open"
                ? _t("Create an open period")
                : _t("Create a closed period");
        return this._openRecord({
            context: creationContext,
            title,
        });
    }
}

registry.category("fields").add("voip_time_condition_periods", {
    ...x2ManyField,
    component: TimeConditionPeriodsField,
});
