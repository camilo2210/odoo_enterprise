import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";

patch(FormController.prototype, {
    async onRootLoaded() {
        await super.onRootLoaded();
        this.env.bus.trigger("VOIP:FORM_CONTROLLER:RECORD_LOADED", {
            resModel: this.props.resModel,
            resId: this.model.root.resId,
        });
    },
});
