import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { OboxActionButton } from "@obox_quality_control/obox_action_button/obox_action_button";
import { browser } from "@web/core/browser/browser";

export class OboxMeasureWidget extends OboxActionButton {
    async onClick() {
        let result;
        try {
            const response = await browser.fetch(`${this.address}/scale/read_scale_weight`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                targetAddressSpace: "local",
                body: JSON.stringify({ identifier: this.identifier }),
            });
            result = await response.json();
        } catch {
            return this.notification.add(_t("Could not get weight."), {
                type: "danger",
            });
        }
        if (!result?.weight) {
            return this.notification.add(result?.error ?? JSON.stringify(result), {
                type: "danger",
            });
        }
        this.props.record.update({ measure: result.weight });
    }
}

registry.category("view_widgets").add("obox_measure", {
    component: OboxMeasureWidget,
    extractProps: ({ attrs }) => ({ btn_name: attrs.btn_name }),
});
