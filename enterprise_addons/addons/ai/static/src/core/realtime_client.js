import { AITranscriptionEvent, transcriptionBus } from "@ai/core/transcription_bus";

export default class RealtimeClient {
    /**
     * @type {RealtimeClient}
     */
    static instance = null;

    constructor() {
        /** @type {WebSocket} */
        this.socket = null;

        this.messageListener = (event) => {
            const jsonData = JSON.parse(event.data);
            transcriptionBus.trigger(AITranscriptionEvent.REALTIME_CLIENT_MESSAGE, jsonData);
        };
    }

    /**
     * @returns {RealtimeClient} the instance of the RealtimeClient
     */
    static getInstance() {
        if (RealtimeClient.instance === null) {
            RealtimeClient.instance = new RealtimeClient();
        }
        return RealtimeClient.instance;
    }

    /**
     * Starts the websocket connection
     *
     * @param {String} sessionToken
     */
    connect(sessionToken) {
        this.socket = new WebSocket("wss://api.openai.com/v1/realtime", [
            "realtime",
            `openai-insecure-api-key.${sessionToken}`,
        ]);

        this.socket.addEventListener("message", this.messageListener);
    }

    /**
     * Sends audio data to the provider
     *
     * @param {Uint8Array} buffer the data to send
     */
    send(buffer) {
        if (this.socket !== null && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(
                JSON.stringify({
                    type: "input_audio_buffer.append",
                    audio: btoa(String.fromCharCode(...buffer)),
                })
            );
        }
    }

    disconnect() {
        if (this.socket !== null) {
            this.socket.close();
            this.socket.removeEventListener("message", this.messageListener);
            this.socket = null;
        }
    }
}
