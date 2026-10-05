import { Component, proxy, useProps, t } from "@odoo/owl";
import { PlatformOrderProvider } from "@pos_platform_order/app/models/platform_order_provider";

export class ProviderLogo extends Component {
    static template = "pos_platform_order.ProviderLogo";
    props = useProps({
        provider: t.instanceOf(PlatformOrderProvider),
    });

    setup() {
        this.state = proxy({
            src: this.props.provider.imageUrl,
        });
    }

    onLoadFailed() {
        this.state.src = "/web/static/img/placeholder.png";
    }
}
