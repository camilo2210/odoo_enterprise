import { Component, proxy, t, useProps, usePlugin } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ORM } from "@web/core/orm_plugin";

export class RefreshButton extends Component {
    static template = "account_online_payment.RefreshButton";
    props = useProps({
        record: t.object(),
    });
    orm = usePlugin(ORM);

    setup() {
        this.state = proxy({
            isFetching: false,
        });
    }

    get paymentOnlineStatus() {
        return this.props.record.data.payment_online_status;
    }

    async onClickFetchStatus() {
        this.state.isFetching = true;

        try {
            await this.orm.call("account.online.link", "check_online_payment_status", [
                this.props.record.resId,
                this.props.record.resModel,
            ]);
        } finally {
            this.props.record.model.load();
            this.state.isFetching = false;
        }
    }
}

export const refreshButtonComp = {
    component: RefreshButton,
};

registry.category("fields").add("account_online_payment_refresh_button", refreshButtonComp);
