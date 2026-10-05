import { Dialog } from "@web/core/dialog/dialog";
import { cookie } from "@web/core/browser/cookie";
import { useService } from "@web/core/utils/hooks";

import { Component, t, useProps } from "@odoo/owl";

export class PhoneInstallDialog extends Component {
    static template = "web_enterprise.PhoneInstallDialog";
    static components = { Dialog };
    props = useProps({
        close: t.function(),
    });

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.ui = useService("ui");
    }

    get screenshotProductionSrc() {
        return cookie.get("color_scheme") === "dark" ?
            "/web_enterprise/static/src/img/phone_install_production_dark.png?v=production-call" :
            "/web_enterprise/static/src/img/phone_install_production.png?v=production-call";
    }

    get screenshotDemoSrc() {
        return cookie.get("color_scheme") === "dark" ?
            "/web_enterprise/static/src/img/phone_install_demo_dark.png?v=willie-burke-equal-height" :
            "/web_enterprise/static/src/img/phone_install_demo.png?v=willie-burke-equal-height";
    }

    async onClickInstall() {
        this.ui.block();
        try {
            const [module] = await this.orm.searchRead(
                "ir.module.module",
                [["name", "=", "voip"]],
                ["id"],
                { limit: 1 }
            );
            const action = await this.orm.call("ir.module.module", "button_immediate_install", [
                [module.id],
            ]);
            await this.action.doAction(action);
        } finally {
            this.ui.unblock();
        }
    }
}
