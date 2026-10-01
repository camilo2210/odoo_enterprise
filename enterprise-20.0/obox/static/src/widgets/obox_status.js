import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Component, onWillUnmount, proxy, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const WS_INTERVAL_CHECK = 15000;
const WAN_PING_TIMEOUT = WS_INTERVAL_CHECK * 2;

export class OboxStatus extends Component {
    static template = "obox.OboxStatus";

    props = useProps(standardWidgetProps);

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({
            wan: {
                status: false,
                lastPing: null,
                lastChecked: null,
            },
            lan: {
                status: false,
                lastChecked: null,
            },
        });
        this.destroyed = false;

        if (this.props.record.resId) {
            const busService = useService("bus_service");
            busService.addChannel(this.props.record.data.internal_websocket_channel);

            const onPing = this.wanOboxStatus.bind(this);
            const onOboxUpdated = this.oboxUpdated.bind(this);
            busService.subscribe("PING", onPing);
            busService.subscribe("OBOX_UPDATED", onOboxUpdated);

            this.startMonitoring();

            onWillUnmount(() => {
                this.destroyed = true;
                busService.unsubscribe("PING", onPing);
                busService.unsubscribe("OBOX_UPDATED", onOboxUpdated);
                clearTimeout(this.currentTimeout);
            });
        }
    }

    isCurrentOboxMessage(data) {
        return data.id === this.props.record.resId;
    }

    wanOboxStatus(data) {
        // Every box the page listens to pings on the same message type: the
        // token tells which box this ping comes from.
        if (this.props.record.data.external_websocket_channel !== `obox_${data.token}`) {
            return;
        }
        this.state.wan.lastPing = Date.now();
        this.state.wan.status = true;
        this.state.wan.lastChecked = new Date();
    }

    async oboxUpdated(data) {
        if (!this.isCurrentOboxMessage(data)) {
            return;
        }
        await this.props.record.load();
        this.checkNow?.();
    }

    get localAddress() {
        const { local_address, local_ip } = this.props.record.data;
        return local_address || local_ip;
    }

    get wanPending() {
        return this.state.wan.lastPing === null;
    }

    get lanPending() {
        return this.state.lan.lastChecked === null;
    }

    get boxAnsweredRecently() {
        const { lastPing } = this.state.wan;
        return lastPing !== null && Date.now() - lastPing < WAN_PING_TIMEOUT;
    }

    get lanTitle() {
        if (this.lanPending) {
            return false;
        }
        return this.state.lan.status
            ? _t("Local Network reachable")
            : _t("Local Network unreachable");
    }

    get wanTitle() {
        if (this.wanPending) {
            return false;
        }
        return this.state.wan.status ? _t("WebSocket connected") : _t("WebSocket disconnected");
    }

    async startMonitoring() {
        const checkWan = async () => {
            try {
                await this.orm.call("obox.obox", "action_check_websocket", [
                    this.props.record.resId,
                ]);
                this.state.wan.status = this.boxAnsweredRecently;
            } catch {
                this.state.wan.status = false;
            } finally {
                this.state.wan.lastChecked = new Date();
            }
        };

        const checkLan = async () => {
            if (!this.localAddress) {
                await this.props.record.load();
                this.state.lan.status = false;
                this.state.lan.lastChecked = new Date();
                return;
            }

            try {
                const url = `http://${this.localAddress}/odoo/`;
                const response = await browser.fetch(url, {
                    signal: AbortSignal.timeout(1000),
                    targetAddressSpace: "local",
                });
                this.state.lan.status = response.ok;
            } catch {
                this.state.lan.status = false;
            } finally {
                this.state.lan.lastChecked = new Date();
            }
        };

        let checking = false;
        let checkAgain = false;
        const check = async () => {
            if (this.destroyed) {
                return;
            }
            if (checking) {
                checkAgain = true;
                return;
            }
            checking = true;
            clearTimeout(this.currentTimeout);
            try {
                await Promise.all([checkWan(), checkLan()]);
            } finally {
                checking = false;
            }
            if (this.destroyed) {
                return;
            }
            if (checkAgain) {
                checkAgain = false;
                return check();
            }
            this.currentTimeout = setTimeout(check, WS_INTERVAL_CHECK);
        };

        this.checkNow = check;
        check();
    }
}

export const OboxStatusParams = {
    component: OboxStatus,
};

registry.category("view_widgets").add("obox_status", OboxStatusParams);
