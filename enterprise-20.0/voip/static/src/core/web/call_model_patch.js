import { Call } from "@voip/core/common/call_model";
import { serializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import { formatDuration } from "@web/views/fields/formatters";

/** @type {import("models").Call} */
const callPatch = {
    /** @returns {string} */
    get callDate() {
        if (this.state === "terminated") {
            return this.start_date.toLocaleString(luxon.DateTime.TIME_SIMPLE);
        }
        return this.create_date.toLocaleString(luxon.DateTime.TIME_SIMPLE);
    },

    /** @returns {string} */
    get durationString() {
        return formatDuration(
            {
                seconds: this.duration,
            },
            {
                showSeconds: true,
                unit: "seconds",
            }
        );
    },

    async abort() {
        const { store_data } = await this.store.env.services.orm.call("voip.call", "abort_call", [
            [this.id],
        ]);
        this.store.insert(store_data);
    },

    async completeElsewhere() {
        const { store_data } = await this.store.env.services.orm.call(
            "voip.call",
            "complete_call_elsewhere",
            [[this.id]]
        );
        this.store.insert(store_data);
    },

    async end(at = luxon.DateTime.now()) {
        const hasDoneActivity = this.activity_id;
        const { store_data } = await this.store.env.services.orm.call(
            "voip.call",
            "end_call",
            [[this.id]],
            { at: serializeDateTime(at) }
        );
        this.store.insert(store_data);
        if (hasDoneActivity) {
            const activity = this.activity_id;
            await this.activity_id.markAsDone();
            activity.remove();
            // Keep the activity_id to avoid log button showing again
            this.activity_id = activity.id;
        }
    },

    async logToChatter() {
        if (this.activity_id) {
            return;
        }
        const currentController = this.store.env.services.action.currentController;
        const kwargs = {};
        if (
            currentController?.props?.type === "form" &&
            currentController?.props?.resModel &&
            typeof currentController?.currentState?.resId === "number"
        ) {
            kwargs.active_model = currentController.props.resModel;
            kwargs.active_id = currentController.currentState.resId;
        }
        const action = await this.store.env.services.orm.call(
            "voip.call",
            "action_log_call",
            [this.id],
            kwargs
        );
        this.store.env.services.action.doAction(action);
    },

    async miss() {
        const { success, store_data } = await this.store.env.services.orm.call(
            "voip.call",
            "miss_call",
            [[this.id]]
        );
        this.store.insert(store_data);
        if (success) {
            ++this.store.env.services.voip.missedCalls;
        }
    },

    async reject() {
        const { store_data } = await this.store.env.services.orm.call("voip.call", "reject_call", [
            [this.id],
        ]);
        this.store.insert(store_data);
    },

    async start(at = luxon.DateTime.now()) {
        const { store_data } = await this.store.env.services.orm.call(
            "voip.call",
            "start_call",
            [[this.id]],
            { at: serializeDateTime(at) }
        );
        this.store.insert(store_data);
    },
};

patch(Call.prototype, callPatch);
