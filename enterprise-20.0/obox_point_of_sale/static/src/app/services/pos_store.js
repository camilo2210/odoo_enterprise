import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { OboxProxy } from "../utils/obox_proxy";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.obox = new OboxProxy({
            data: this.data,
            createJob: this.createJob.bind(this),
            checkJob: this.checkJob.bind(this),
        });
    },
    async createJob({ oboxId, payload }) {
        try {
            return await this.data.call("obox.obox", "create_job", [oboxId, payload]);
        } catch (error) {
            console.error("Failed to create OBOX job:", error);
        }
    },
    async checkJob(uuid) {
        try {
            return await this.data.call("obox.queue", "check_job_status", [uuid]);
        } catch (error) {
            console.error("Failed to check OBOX job status:", error);
        }
    },
});
