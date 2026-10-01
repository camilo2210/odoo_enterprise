import { registry } from "@web/core/registry";

export class VoipWorkerClient {
    constructor(voip, workerService) {
        this.voip = voip;
        this.workerService = workerService;
    }

    handleMessage(message) {
        const { type, data } = message.data;
        if (!type?.startsWith("VOIP:")) {
            return;
        }
        switch (type) {
            case "VOIP:PLAY_INCOMING":
                this._onPlayIncoming(data.sessionKey);
                break;
            default:
                console.warn(`VoIP Worker Service received unknown message type: “${type}”`);
        }
    }

    send(action, data) {
        this.workerService.send(action, data);
    }

    _onPlayIncoming(sessionKey) {
        const session = this.voip.userAgent.sessions[sessionKey];
        if (!session) {
            return;
        }
        session.ringleader = true;
        this.voip.userAgent.requestIncomingRingtone();
    }
}

export const voipWorkerService = {
    dependencies: ["voip", "worker_service"],
    start(_env, { voip, worker_service: workerService }) {
        const client = new VoipWorkerClient(voip, workerService);
        workerService.registerHandler(client.handleMessage.bind(client));
        return client;
    },
};

registry.category("services").add("voip.worker", voipWorkerService);
