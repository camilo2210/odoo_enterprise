import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";

const CONSOLE_COLOR = "#57F7FF";

export class OboxProxy {
    constructor({ data, bus, createJob, checkJob }) {
        this.data = data;
        this.bus = bus;
        this.createJob = createJob;
        this.checkJob = checkJob;
        this.uuids = new Map();

        this.initializeWebsocketChannel();
    }

    initializeWebsocketChannel() {
        this.data.connectWebSocket("OBOX", this.handleOboxMessage.bind(this));
    }

    async waitForJobCompletion(uuid, timeout) {
        return new Promise((resolve, reject) => {
            this.uuids.set(uuid, resolve);
            setTimeout(async () => {
                if (this.uuids.has(uuid)) {
                    // Proceed to a manual check in case of websocket message loss
                    const manualCheckResult = await this.performManualCheck(uuid, resolve);
                    if (!manualCheckResult) {
                        this.uuids.delete(uuid);
                        reject(new Error(`OBOX job timed out: ${uuid}`));
                    }
                }
            }, timeout);
        });
    }

    async createOboxJob(opts, timeout = 10000) {
        const uuids = await this.createJob(opts);
        if (uuids && uuids.length > 0) {
            logPosMessage(
                "OboxProxy",
                "createOboxJob",
                `New OBOX job created: ${uuids.join(", ")}`,
                CONSOLE_COLOR
            );

            const promises = [];
            for (const uuid of uuids) {
                promises.push(this.waitForJobCompletion(uuid, timeout));
            }
            return Promise.all(promises);
        }
    }

    async performManualCheck(uuid, resolver) {
        // Proceed to a manual check in case of websocket message loss
        try {
            const jobs = await this.checkJob(uuid);
            const job = jobs[0];
            if (job.status !== "done") {
                return false;
            }

            logPosMessage(
                "OboxProxy",
                "performManualCheck",
                `OBOX job completed after timeout: ${uuid}`,
                CONSOLE_COLOR
            );
            resolver(job.result || true);
            return true;
        } catch (e) {
            logPosMessage(
                "OboxProxy",
                "performManualCheck",
                `Failed to fetch OBOX job after timeout: ${uuid}`,
                "#FF0000",
                [e]
            );
            return false;
        }
    }

    handleOboxMessage(data) {
        const uuid = data.uuid;
        if (this.uuids.has(uuid)) {
            logPosMessage(
                "OboxProxy",
                "handleOboxMessage",
                `OBOX job completed: ${uuid}`,
                CONSOLE_COLOR
            );
            const resolver = this.uuids.get(uuid);
            resolver(data.result || true);
            this.uuids.delete(uuid);
        } else {
            logPosMessage(
                "OboxProxy",
                "handleOboxMessage",
                `Received OBOX message for unknown job: ${uuid}`,
                CONSOLE_COLOR
            );
        }
    }
}
