import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, markup, proxy, useProps, usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";

class BankJournalStatus extends Component {
    static template = "account_online_synchronization.BankJournalStatus";
    props = useProps(standardWidgetProps);
    orm = usePlugin(ORM);

    setup() {
        this.actionService = useService("action");
        this.busService = useService("bus_service");

        this.state = proxy({
            isFetchingHovered: false,
            isConsentHovered: false,
            connectionStateDetails: null,
        });

        onWillStart(() => {
            const kanbanDashboardData = JSON.parse(this.recordData.kanban_dashboard || "{}");
            this.state.connectionStateDetails = kanbanDashboardData?.connection_state_details;
        });

        this.busService.subscribe("online_sync", (notification) => {
            if (notification?.id === this.recordId && notification?.connection_state_details) {
                this.state.connectionStateDetails = notification.connection_state_details;
            }
        });
    }

    onMouseEnterFetching() {
        this.state.isFetchingHovered = true;
    }

    onMouseLeaveFetching() {
        this.state.isFetchingHovered = false;
    }

    onMouseEnterConsent() {
        this.state.isConsentHovered = true;
    }

    onMouseLeaveConsent() {
        this.state.isConsentHovered = false;
    }

    refreshFetching() {
        this.actionService.restore(this.actionService.currentController.jsId);
    }

    async fetchTransactions() {
        this.state.connectionStateDetails = { status: "fetching" };

        const action = await this.orm.call("account.journal", "manual_sync", [this.recordId]);
        if (action) {
            action.help = markup(action.help);
            this.actionService.doAction(action);
        }
    }

    async openAsyncAction() {
        this.actionService.doActionButton({
            type: "object",
            resModel: "account.journal",
            name: "action_open_dashboard_asynchronous_action",
            resIds: [this.recordId],
        });
        this.state.connectionStateDetails = null;
    }

    async extendConnection() {
        this.actionService.doActionButton({
            type: "object",
            resModel: "account.journal",
            name: "action_extend_consent",
            resIds: [this.recordId],
        });
    }

    async reconnectJournal() {
        let method;
        if (this.isInError || this.isFetchingFailed) {
            method = "manual_sync";
        } else {
            // Implicit way to say that the account is disconnected
            method = "action_reconnect_online_account";
        }
        const action = await this.orm.call("account.journal", method, [this.recordId]);
        if (action) {
            this.actionService.doAction(action);
        }
    }

    get recordId() {
        return this.props.record.resId;
    }

    get recordData() {
        return this.props.record.data;
    }

    get hasOnlineAccount() {
        return !!this.recordData.account_online_account_id;
    }

    get onlineLinkState() {
        return this.recordData.account_online_link_state;
    }

    get expiringDate() {
        return this.recordData.expiring_synchronization_date;
    }

    get expiringDueDays() {
        return this.recordData.expiring_synchronization_due_day;
    }

    get isConnected() {
        return this.onlineLinkState === "connected";
    }

    get isDisconnected() {
        return this.onlineLinkState === "disconnected";
    }

    get isInError() {
        return this.onlineLinkState === "error";
    }

    get isExpired() {
        return (
            this.expiringDate &&
            typeof this.expiringDueDays === "number" &&
            this.expiringDueDays <= 0
        );
    }

    get isExpiringSoon() {
        return (
            this.expiringDate &&
            typeof this.expiringDueDays === "number" &&
            this.expiringDueDays <= 7
        );
    }

    get isExpiringCritical() {
        return (
            this.expiringDate &&
            typeof this.expiringDueDays === "number" &&
            this.expiringDueDays <= 3
        );
    }

    get connectionStatus() {
        return this.state.connectionStateDetails?.status;
    }

    get isFetching() {
        return this.connectionStatus === "fetching";
    }

    get isFetchingSucceed() {
        return this.connectionStatus === "success";
    }

    get isFetchingFailed() {
        return this.connectionStatus === "error";
    }

    get errorType() {
        return this.state.connectionStateDetails?.error_type;
    }

    get nbFetchedTransactions() {
        return this.state.connectionStateDetails?.nb_fetched_transactions || 0;
    }

    get shouldShowReconnectButton() {
        return this.isExpired || this.isInError || this.isFetchingFailed || this.isDisconnected;
    }

    get shouldShowExpirationInfo() {
        // The condition on isExpired should be the inverse of the one in shouldShowReconnectButton
        return this.isConnected && this.expiringDate && !this.isExpired;
    }

    get formattedExpirationDate() {
        if (!this.expiringDate) {
            return "";
        }
        return new Date(this.expiringDate).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
        });
    }

    get cssClasses() {
        let classes = "text-nowrap w-100";
        if (this.isExpiringSoon) {
            classes += this.isExpiringCritical ? " text-danger" : " text-warning";
        }
        if (this.props.mode === "compact") {
            classes += " d-flex align-items-center";
        }
        return classes;
    }
}

export const bankJournalStatus = {
    component: BankJournalStatus,
};

registry.category("view_widgets").add("bank_journal_status", bankJournalStatus);
