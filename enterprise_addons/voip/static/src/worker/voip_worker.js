export class VoipWorker {
    callById = new Map();

    constructor() {
        setInterval(() => this.freeOldRefs(), 3600 * 1000);
    }

    handleMessage(event) {
        const { action } = event.data;
        if (!action?.startsWith("VOIP:")) {
            return;
        }
        switch (action) {
            case "VOIP:RING?": {
                this._onRing(event);
                break;
            }
            default:
                console.warn("Unknown message action:", action);
        }
    }

    /**
     * Clears callById from old calls, enabling their garbage collection.
     */
    freeOldRefs() {
        const now = Date.now();
        for (const [id, call] of this.callById) {
            if (call.expires <= now) {
                this.callById.delete(id);
            }
        }
    }

    _onRing({ target: client, data: { data } }) {
        const { controlHandle, sessionKey } = data;
        if (this.callById.has(controlHandle)) {
            return;
        }
        const call = { expires: Date.now() + 10 * 60 * 1000 };
        this.callById.set(controlHandle, call);
        client.postMessage({ type: "VOIP:PLAY_INCOMING", data: { sessionKey } });
    }
}
