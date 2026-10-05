import { registry } from "@web/core/registry";
import { LazyComponent } from "@web/core/lazy_component";
import { cookie } from "@web/core/browser/cookie";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

import { Component, t, useProps, xml } from "@odoo/owl";

class StudioActionLoader extends Component {
    static components = { LazyComponent };
    static template = xml`
        <LazyComponent bundle="this.bundle" Component="'StudioClientAction'" props="this.props"/>
    `;
    props = useProps({
        ...standardActionServiceProps,
        props: t.object().optional(),
        Component: t.function().optional(),
    });
    setup() {
        this.bundle =
            cookie.get("color_scheme") === "dark"
                ? "web_studio.studio_assets_dark"
                : "web_studio.studio_assets";
    }
}
registry.category("actions").add("studio", StudioActionLoader);
