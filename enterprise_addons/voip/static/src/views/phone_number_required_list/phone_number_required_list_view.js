import { onWillStart, props, t } from "@odoo/owl";
import { NoPhoneNumberCard } from "@voip/core/web/no_phone_number_card";
import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer, listRendererProps } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";

export class PhoneNumberRequiredListController extends ListController {
    static template = "voip.PhoneNumberRequiredListView";

    setup() {
        super.setup();
        this.hasPhoneNumber = false;
        onWillStart(async () => {
            this.hasPhoneNumber = Boolean(
                await this.orm.searchCount("voip.did.number", [
                    ["state", "not in", ["released", "failure"]],
                ])
            );
            if (!this.hasPhoneNumber) {
                this.activeActions.create = false;
            }
        });
    }
}

export class PhoneNumberRequiredListRenderer extends ListRenderer {
    static template = "voip.PhoneNumberRequiredListRenderer";
    static components = {
        ...ListRenderer.components,
        NoPhoneNumberCard,
    };
    props = props({
        ...listRendererProps,
        hasPhoneNumber: t.boolean(),
    });
}

export const phoneNumberRequiredListView = {
    ...listView,
    Controller: PhoneNumberRequiredListController,
    Renderer: PhoneNumberRequiredListRenderer,
};

registry.category("views").add("voip_phone_number_required_list", phoneNumberRequiredListView);
