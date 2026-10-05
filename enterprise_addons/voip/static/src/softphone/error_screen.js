import { Component, t, useProps } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";

export class ErrorScreen extends Component {
    static template = "voip.ErrorScreen";

    props = useProps({
        isBlocking: t.boolean(),
        isConnecting: t.boolean(),
        message: t.string().optional(),
        technical: t.string().optional(),
        technicalExtra: t.string().optional(),
        buyCreditsUrl: t.string().optional(),
    });

    setup() {
        this.voip = useService("voip");
    }

    onClickCloseButton() {
        this.voip.resolveError();
    }
}
