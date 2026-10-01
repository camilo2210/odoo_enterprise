import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { OboxActionButton } from "@obox_quality_control/obox_action_button/obox_action_button";
import { browser } from "@web/core/browser/browser";

export class OboxPictureWidget extends OboxActionButton {
    async onClick() {
        let result;
        try {
            const response = await browser.fetch(
                `${this.address}/camera/take-picture?identifier=${this.identifier}`,
                {
                    targetAddressSpace: "local",
                }
            );
            result = await response.json();
        } catch {
            return this.notification.add(_t("Could not capture image."), {
                type: "danger",
            });
        }
        if (!result.image) {
            return this.notification.add(result?.error ?? JSON.stringify(result), {
                type: "danger",
            });
        }
        this.notification.add(_t("Image captured successfully"), { type: "success" });
        this.props.record.update({ picture: result.image });
    }
}

registry.category("view_widgets").add("obox_picture", {
    component: OboxPictureWidget,
    extractProps: ({ attrs }) => ({ btn_name: attrs.btn_name }),
});
