import { Component, t, useProps } from "@odoo/owl";
import { useSignViewButtons } from "@sign/views/hooks";
import { useService } from "@web/core/utils/hooks";

export class SignActionHelper extends Component {
    static template = "sign.SignActionHelper";

    props = useProps({
        resModel: t.any(),
    });

    setup() {
        this.actionService = useService("action");
        this.signButtons = useSignViewButtons({ ignoreBusSubscription: true });
    }

    onClickUpload(context) {
        return this.signButtons.requestFile(context);
    }

    onClickSampleSign() {
        return this.actionService.doAction("sign.sign_template_tour_trigger_action");
    }
}
