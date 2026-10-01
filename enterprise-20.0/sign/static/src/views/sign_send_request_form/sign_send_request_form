import { useSubEnv } from "@web/owl2/utils";
import { formView } from "@web/views/form/form_view";
import { formControllerProps } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { EventBus, useProps, t } from "@odoo/owl";

export class SignSendRequestController extends formView.Controller {
    props = useProps({
        ...formControllerProps,
        fullComposerBus: t.instanceOf(EventBus).optional(new EventBus()),
    });
    setup() {
        super.setup();
        useSubEnv({
            fullComposerBus: this.props.fullComposerBus,
        });
    }
}

registry.category("views").add("sign_send_request_form", {
    ...formView,
    Controller: SignSendRequestController,
});
