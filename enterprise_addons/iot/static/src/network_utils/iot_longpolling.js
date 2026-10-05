import { registry } from "@web/core/registry";
import { post } from "@iot/network_utils/http";
import { uuid } from "@web/core/utils/strings";
import { _t } from "@web/core/l10n/translation";

/**
 * @typedef {{
 *   last_event: number;
 *   devices: Record<string, { callback: (message: any) => void }>;
 *   session_id: string;
 *   abortController: AbortController | null;
 *   useLna: boolean;
 * }} Listener
 */

export class IoTLongpolling {
    static serviceDependencies = ["notification"];
    actionRoute = "/iot_drivers/action";
    pollRoute = "/iot_drivers/event";

    rpcDelay = 1500;
    maxRpcDelay = 15000;

    _retries = 0;
    /** @type {Record<string, Listener>} */
    _listeners = {};

    constructor() {
        this.setup(...arguments);
    }

    /**
     * Setup in addition to constructor to allow patching
     */
    setup({ notification }) {
        this.notification = notification;
    }

    /**
     * Send a message to the IoT Box (action route)
     * @param {string} iotBoxIp IP Address of the IoT Box
     * @param {Object} message Data to send to the device
     * @param {string} [messageId] Unique identifier for the message
     * @param {boolean} [fallback] If longpolling has a fallback option (e.g. websocket), do not display errors to the user
     * @param {boolean} [useLna] if true, always use HTTP even in HTTPS context
     * @returns {Promise<*>} response of the request (response.result tells if the device is connected or not)
     */
    async sendMessage(iotBoxIp, message, messageId = null, fallback = false, useLna = false) {
        messageId ??= uuid();
        const response = await this.rpc(
            iotBoxIp,
            { session_id: messageId, ...message },
            { fallback, useLna }
        );
        return response?.result;
    }

    /**
     * Listen for messages from the IoT Box (polling the IoT Box)
     * @param {string} iotBoxIp IP Address of the IoT Box
     * @param {string} iotDeviceIdentifier Identifier of the device connected to the IoT Box
     * @param {(message: { status: string, [key: string]: any }) => void} onSuccess Callback to run when a successful response is received
     * @param {(message: { status: string, [key: string]: any }) => void} onFailure Callback to run when the request fails
     * @param {string} [sessionId] The request ID to listen for (optional)
     * @param {boolean} [useLna] if true, always use HTTP even in HTTPS context
     */
    async onMessage(
        iotBoxIp,
        iotDeviceIdentifier,
        onSuccess = () => {},
        onFailure = () => {},
        sessionId = null,
        useLna = false
    ) {
        const { promise, resolve, reject } = Promise.withResolvers();

        const listenerCallback = (message) => {
            this.removeListener(iotBoxIp, iotDeviceIdentifier);
            if (message.status === "unreachable") {
                reject(new Error("IoT box is unreachable"));
                return;
            }
            const callback =
                message.status === "success" || message.status?.status === "connected"
                    ? onSuccess
                    : onFailure;
            callback(message);
            resolve();
        };
        await this.addListener(
            iotBoxIp,
            [iotDeviceIdentifier],
            sessionId,
            listenerCallback,
            true,
            useLna
        );

        return promise;
    }

    /**
     * Add a deviceIdentifier to listeners[iot_ip] and restart polling
     *
     * @param {string} iotBoxIp
     * @param {Array} deviceIdentifiers list of device identifiers
     * @param {string} [listenerId]
     * @param {boolean} fallback if true, no notification will be displayed on fail
     * @param {(message: any) => void} callback
     * @param {boolean} [useLna] if true, always use HTTP even in HTTPS context
     */
    async addListener(
        iotBoxIp,
        deviceIdentifiers,
        listenerId,
        callback,
        fallback = true,
        useLna = false
    ) {
        const listener = (this._listeners[iotBoxIp] ??= {
            last_event: 0,
            devices: {},
            session_id: listenerId || uuid(),
            abortController: null,
            useLna,
        });

        for (const identifier of deviceIdentifiers) {
            listener.devices[identifier] = { callback };
        }
        this.stopPolling(iotBoxIp);
        this.poll(iotBoxIp, fallback, useLna);
    }

    /**
     * Stop listening to iot device with id `deviceIdentifier`
     * @param {string} iotBoxIp
     * @param {string} deviceIdentifier
     */
    removeListener(iotBoxIp, deviceIdentifier) {
        const listener = this._listeners[iotBoxIp];
        const device = listener.devices[deviceIdentifier];
        if (device) {
            delete listener.devices[deviceIdentifier];
            if (!Object.keys(listener.devices).length) {
                this.stopPolling(iotBoxIp);
            }
        }
    }

    startPollingAll() {
        for (const ip of Object.keys(this._listeners)) {
            this.poll(ip, false, this._listeners[ip].useLna);
        }
    }

    /**
     * Stops any started long polling
     *
     * Aborts a pending long-poll so that we immediately remove ourselves
     * from listening on notifications on this channel.
     */
    stopPolling(iotBoxIp) {
        if (this._listeners[iotBoxIp].abortController) {
            this._listeners[iotBoxIp].abortController.abort();
            this._listeners[iotBoxIp].abortController = null;
        }
    }

    /**
     * Execute an RPC to the box
     * Used to do both polling or action
     *
     * @param {string} iotBoxIp IP of the IoT Box
     * @param {Object} params information needed to perform an action or the listener for the polling
     * @param {string} [route] endpoint to call on the IoT Box (default to actionRoute)
     * @param {number} [timeout] time before the request times out (undefined to use default timeout from http.js)
     * @param {AbortSignal} [signal] AbortSignal to cancel the request
     * @param {boolean} [fallback] if true, no notification will be displayed on fail
     * @param {boolean} [useLna] if true, always use HTTP even in HTTPS context
     */
    async rpc(
        iotBoxIp,
        params,
        { route = this.actionRoute, timeout, signal, fallback = false, useLna = false } = {}
    ) {
        try {
            return await post(iotBoxIp, route, params, timeout, signal, useLna);
        } catch (error) {
            if (!fallback && error?.name !== "AbortError") {
                this._doWarnFail(iotBoxIp);
            }
            throw new Error("Longpolling RPC Error", { cause: error });
        }
    }

    /**
     * Make a poll request to an IoT Box
     *
     * @param {string} iotBoxIp
     * @param {boolean} fallback if true, no notification will be displayed on fail
     * @param {boolean} [useLna] if true, always use HTTP even in HTTPS context
     */
    async poll(iotBoxIp, fallback = true, useLna = false) {
        const listener = this._listeners[iotBoxIp];
        if (!listener || listener.abortController) {
            return;
        }

        const abortController = new AbortController();
        listener.abortController = abortController;

        // The backend has a maximum cycle time of 50 seconds so give +10 seconds
        try {
            const { result } = await this.rpc(
                iotBoxIp,
                { listener },
                {
                    route: this.pollRoute,
                    timeout: 60000,
                    signal: abortController.signal,
                    fallback,
                    useLna,
                }
            );
            this._retries = 0;
            listener.abortController = null;

            if (listener.session_id && result?.session_id === listener.session_id) {
                listener.last_event = result.time;
                listener.devices[result.device_identifier]?.callback(result);
            }

            if (Object.keys(listener.devices).length) {
                this.poll(iotBoxIp, fallback, useLna);
            }
        } catch (e) {
            const errorName = e.cause?.name ?? e.name;
            if (errorName === "AbortError") {
                return;
            }
            if (errorName !== "TimeoutError") {
                this._onPollNetworkError(iotBoxIp);
                return;
            }
            this._retries++;
            setTimeout(
                () => this.startPollingAll(),
                Math.min(this.rpcDelay * this._retries, this.maxRpcDelay)
            );
        }
    }

    _onPollNetworkError(iot_ip) {
        for (const device of Object.values(this._listeners[iot_ip].devices)) {
            device.callback({ status: "unreachable" });
        }
    }

    /**
     * This method is needed in _poll.
     * @param {string} url
     */
    _doWarnFail(url) {
        this.notification.add(_t("Failed to reach IoT Box at %s", url), {
            title: _t("Connection to IoT Box failed"),
            type: "danger",
        });
    }
}

export const iotLongpollingService = {
    dependencies: IoTLongpolling.serviceDependencies,
    start(_, deps) {
        return new IoTLongpolling(deps);
    },
};

registry.category("services").add("iot_longpolling", iotLongpollingService);
