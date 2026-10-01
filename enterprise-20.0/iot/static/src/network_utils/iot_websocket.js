import { uuid } from "@web/core/utils/strings";

/**
 * Class to handle Websocket connections
 */
export class IotWebsocket {
    constructor() {
        this.setup(...arguments);
        this._listeners = new Map();
    }

    /**
     * @param {import("services").ServiceFactories} services
     */
    async setup({ bus_service, orm, lazy_session }) {
        this.busService = bus_service;
        this.orm = orm;
        if (lazy_session) {
            lazy_session.getValue("iot_channel", (iotChannel) => {
                this.iotChannel = iotChannel;
            });
        } else {
            this.iotChannel = await this.orm.call("iot.channel", "get_iot_channel");
        }
    }

    /**
     * Send a message to the IoT Box
     * @param {string} iotBoxIdentifier Identifier of the IoT Box
     * @param {Record<string, any>} message Data to send to the device
     * @param {string} messageId Unique identifier for the message (optional)
     * @param {string} messageType Type of message to send (optional)
     * @returns {Promise<string>} The message ID
     */
    async sendMessage(iotBoxIdentifier, message, messageId = null, messageType = "iot_action") {
        messageId ??= uuid();

        await this.orm.call("iot.channel", "send_message", [
            { iot_identifier: iotBoxIdentifier, session_id: messageId, ...message },
            messageType,
        ]);

        return messageId;
    }

    /**
     * Add a listener for events/messages coming from the IoT Box.
     * This method allows defining callbacks for success and failure cases.
     * @param {string} iotBoxIdentifier Identifier of the IoT Box
     * @param {string} deviceIdentifier Identifier of the device connected to the IoT Box
     * @param {(message: { status: string, [key: string]: any }) => void} onSuccess Callback to run when a message is received
     * @param {(message: { status: string, [key: string]: any }) => void} onFailure Callback to run when the request fails
     * @param {string} messageType The type of message to listen for (optional)
     * @param {string} sessionId The session ID to listen for (optional)
     */
    onMessage(
        iotBoxIdentifier,
        deviceIdentifier,
        onSuccess = () => {},
        onFailure = () => {},
        messageType = "operation_confirmation",
        sessionId = null
    ) {
        if (!this.iotChannel) {
            console.error("No IoT Channel found");
            return;
        }

        const key = `${iotBoxIdentifier}:${deviceIdentifier}:${messageType}`;
        this._listeners.get(key)?.();

        const timeoutId = setTimeout(() => {
            console.debug("Websocket timeout for", iotBoxIdentifier, deviceIdentifier, sessionId);
            onFailure(
                {
                    status: "timeout",
                    message: "Timeout waiting for IoT Box response, please try again.",
                },
                deviceIdentifier,
                sessionId
            );
            cleanup();
        }, 6000); // error callback if the listener is not called within 6 seconds

        const messageCallback = (event) => {
            const { session_id, iot_box_identifier, device_identifier, message } = event;
            if (
                iot_box_identifier !== iotBoxIdentifier ||
                device_identifier !== deviceIdentifier ||
                (sessionId && session_id !== sessionId)
            ) {
                return;
            }

            if (message.status === "duplicate") {
                // action already sent through lp, we still expect answer from ws
                return;
            }

            const callback =
                message.status === "success" || message.status?.status === "connected"
                    ? onSuccess
                    : onFailure;
            callback(message);
            cleanup();
        };

        const cleanup = () => {
            clearTimeout(timeoutId);
            this.busService.unsubscribe(messageType, messageCallback);
            this._listeners.delete(key);
        };
        this._listeners.set(key, cleanup);

        this.busService.addChannel(this.iotChannel);
        this.busService.subscribe(messageType, messageCallback);
    }
}
