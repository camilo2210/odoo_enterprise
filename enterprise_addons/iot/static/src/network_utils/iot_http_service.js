import { registry } from "@web/core/registry";
import { post } from "@iot/network_utils/http";
import { uuid } from "@web/core/utils/strings";
import { IotWebsocket } from "@iot/network_utils/iot_websocket";
import { _t } from "@web/core/l10n/translation";

export const PRINTER_MESSAGES = {
    ERROR_FAILED: _t("Failed to initiate print"),
    ERROR_TIMEOUT: _t("Printing timed out"),
    ERROR_UNREACHABLE: _t("Printer is unreachable"),
    ERROR_UNKNOWN: _t("Unknown printer error occurred"),
};

export const FDM_MESSAGES = {
    "000": _t("Blackbox is running and operational"),
    "001": _t("PIN accepted."),
    101: _t("Fiscal Data Module memory 90% full."),
    102: _t("Repeated request. This request was already handled by the fiscal data module."),
    103: _t("Operation wasn't saved on the blackbox"),
    199: _t("Unspecified warning."),
    201: _t("No Vat Signing Card or Vat Signing Card broken."),
    202: _t("Please activate the Vat Signing Card with PIN."),
    203: _t("Vat Signing Card blocked."),
    204: _t("Invalid PIN."),
    205: _t("Fiscal Data Module memory full."),
    206: _t("Unknown identifier."),
    207: _t("Invalid data in message sent to the blackbox."),
    208: _t("Fiscal Data Module not operational. Please restart the blackbox"),
    209: _t("Fiscal Data Module real time clock corrupt."),
    210: _t("Vat Signing Card not compatible with Fiscal Data Module."),
    299: _t("Unspecified error."),
    300: _t(
        "Blackbox responded with invalid response. Please check the cable connection and the power supply, then retry. Restart if necessary"
    ),
    301: _t(
        "Blackbox did not respond to your request. This usually means it has disconnected. Please check its cable connection and its power supply. Restart if necessary."
    ),
    426: _t(
        "Blackbox driver update required. Please restart your IoT Box to update the blackbox driver."
    ),
};

/**
 * Class to handle IoT actions
 * The class is used to send actions to IoT devices and handle fallbacks
 * in case the request fails: it will try to send the request using
 * HTTP POST method and then using the websocket.
 */
export class IotHttpService {
    connectionStatus = "longpolling"; // longpolling, websocket, offline
    connectionTypes = [this._longpolling.bind(this), this._websocket.bind(this)];
    cachedIotBoxes = {};

    constructor() {
        this.setup(...arguments);
    }

    /**
     * @param {import("services").ServiceFactories & { websocket: IotWebsocket } }} services
     */
    setup({ iot_longpolling, websocket, notification, orm }) {
        this.longpolling = iot_longpolling;
        this.websocket = websocket;
        this.notification = notification;
        this.orm = orm;
        this.lnaInitialised = false;
    }

    onFailure(_message, deviceIdentifier, _messageId) {
        this.notification.add(_t("Failed to reach the IoT Box for device: %s", deviceIdentifier), {
            type: "danger",
        });
    }

    cacheIotBoxRecords(boxes) {
        for (const box of boxes) {
            this.cachedIotBoxes[box.id] = {
                ip: box.ip,
                identifier: box.identifier,
                use_lna: box.use_lna,
            };
        }
    }

    async getIotBoxData(iotBoxId) {
        const records = await this.orm.searchRead(
            "iot.box",
            [["id", "=", iotBoxId]],
            ["id", "ip", "identifier", "use_lna"]
        );
        if (!records.length) {
            throw new Error(`No IoT Box found`);
        }
        if (records[0].use_lna && !this.lnaInitialised) {
            try {
                const result = await navigator.permissions.query({ name: "local-network-access" });
                if (["granted", "prompt"].includes(result?.state)) {
                    this.lnaInitialised = true;
                }

                const message = _t(
                    "Local Network Access permission is denied. Some hardware devices might not work properly. Please allow Local Network Access in your browser settings."
                );
                this.notification.add(message, { type: "warning" });
            } catch {
                const isChromiumBased = navigator.userAgent.includes("Chromium") || !!window.chrome;
                let message;
                if (!isChromiumBased) {
                    message = _t(
                        "Local Network Access configuration is enabled, but your browser is not Chromium-based. Please use a Chromium-based browser to benefit from this feature."
                    );
                } else {
                    message = _t(
                        "Local Network Access is enabled for this IoT box, but your browser version does not support it. Please update your browser to the latest version."
                    );
                }
                this.notification.add(message, { type: "warning" });
            }
        }
        return records;
    }

    async _longpolling({ ip, deviceIdentifier, data, messageId, onSuccess, onFailure, use_lna }) {
        if (data) {
            const response = await this.longpolling.sendMessage(
                ip,
                { device_identifier: deviceIdentifier, data },
                messageId,
                true,
                use_lna
            );
            this.connectionStatus = "longpolling";
            const status = response?.status || "disconnected";
            if (status === "duplicate") {
                return; // ignore duplicates
            }
            if (status !== "success") {
                return onFailure({ status }, deviceIdentifier, messageId);
            }
            if (response?.result !== "pending") {
                // respond directly for devices that don't need async confirmation
                return onSuccess(response, deviceIdentifier, messageId);
            }
        }
        this.connectionStatus = "longpolling";
        return await this.longpolling.onMessage(
            ip,
            deviceIdentifier,
            onSuccess,
            onFailure,
            messageId,
            use_lna
        );
    }

    async _websocket({
        identifier,
        deviceIdentifier,
        data,
        messageId,
        onSuccess,
        onFailure,
        messageType,
    }) {
        const onFailureWithTimeout = (...args) => {
            onFailure(...args);
            this.connectionStatus = "offline";
        };
        this.websocket.onMessage(
            identifier,
            deviceIdentifier,
            onSuccess,
            onFailureWithTimeout,
            "operation_confirmation",
            messageId
        );
        if (data) {
            this.websocket.sendMessage(
                identifier,
                { device_identifier: deviceIdentifier, ...data },
                messageId,
                messageType
            );
        }
        this.connectionStatus = "websocket";
    }

    async _attemptFallbacks({ iotBoxId, deviceIdentifier, data, onFailure }) {
        if (!["number", "string"].includes(typeof iotBoxId)) {
            iotBoxId = iotBoxId?.id; // iotBoxId is the ``Many2one`` field, we need the actual ID
        }

        if (!this.cachedIotBoxes[iotBoxId]) {
            this.cacheIotBoxRecords(await this.getIotBoxData(iotBoxId));
        }
        const { ip, identifier, use_lna } = this.cachedIotBoxes[iotBoxId];

        // if we target the box instead of a device, we want longpolling to handle action as messageType
        const messageType = deviceIdentifier === identifier ? data.action : undefined;
        const params = {
            ip,
            identifier,
            use_lna: use_lna && this.lnaInitialised,
            data,
            messageType,
            ...arguments[0],
        };

        for (const connectionType of this.connectionTypes) {
            try {
                return await connectionType(params);
            } catch (e) {
                console.debug(
                    "IoT Box action: attempted method failed, attempting another protocol.",
                    e
                );
            }
        }

        // If all the connection types failed, run the onFailure callback and remove the cached IoT Box data
        delete this.cachedIotBoxes[iotBoxId];
        this.connectionStatus = "offline";
        onFailure({ status: "disconnected" }, deviceIdentifier);
    }

    /**
     * Listen for events on the IoT Box
     * @param iotBoxId IoT Box record ID
     * @param deviceIdentifier Identifier of the device connected to the IoT Box
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onSuccess Callback to run when a message is received
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onFailure Callback to run when the request fails
     * @param {string|null} messageId Unique identifier for the message (optional)
     * @returns {Promise<void>}
     */
    async onMessage(
        iotBoxId,
        deviceIdentifier,
        onSuccess = () => {},
        onFailure = (...args) => this.onFailure(...args),
        messageId = null
    ) {
        // Attempt to listen for messages using the defined connection types
        await this._attemptFallbacks({
            iotBoxId,
            deviceIdentifier,
            messageId,
            onSuccess,
            onFailure,
        });
    }

    /**
     * Call for an action method on the IoT Box
     * @param iotBoxId IoT Box record ID
     * @param deviceIdentifier Identifier of the device connected to the IoT Box
     * @param data Data to send
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onSuccess Callback to run when a message is received
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onFailure Callback to run when the request fails
     * @param {string|null} messageId Unique identifier for the message (optional)
     * @returns {Promise<void>}
     */
    async action(
        iotBoxId,
        deviceIdentifier,
        data,
        onSuccess = () => {},
        onFailure = (...args) => this.onFailure(...args),
        messageId = null
    ) {
        messageId ??= uuid();

        if (!data) {
            data = {};
        }
        data.action_unique_id = messageId;

        await this._attemptFallbacks({
            iotBoxId,
            deviceIdentifier,
            data,
            messageId,
            onSuccess,
            onFailure,
        });
    }
}

export const iotHttpService = {
    dependencies: ["notification", "orm", "bus_service", "iot_longpolling", "lazy_session"],

    start(env, services) {
        const { iot_longpolling } = services;
        const iotWebsocket = new IotWebsocket(services);

        const iotHttp = new IotHttpService({ ...services, websocket: iotWebsocket });

        return this._getMethodsToExpose(iotHttp, iot_longpolling, iotWebsocket);
    },
    /**
     * Expose only these functions to the environment
     * @param {IotHttpService} iotHttp
     * @param {IoTLongpolling} longpollingService
     * @param {IotWebsocket} websocketService
     */
    _getMethodsToExpose(iotHttp, longpollingService, websocketService) {
        const longpolling = {
            sendMessage: longpollingService.sendMessage.bind(longpollingService),
            onMessage: longpollingService.onMessage.bind(longpollingService),
        };

        const websocket = {
            sendMessage: websocketService.sendMessage.bind(websocketService),
            onMessage: websocketService.onMessage.bind(websocketService),
        };

        const cacheIotBoxRecords = iotHttp.cacheIotBoxRecords.bind(iotHttp);
        const action = iotHttp.action.bind(iotHttp);
        const onMessage = iotHttp.onMessage.bind(iotHttp);

        // status is a getter to have a reactive value
        return {
            post,
            action,
            longpolling,
            websocket,
            onMessage,
            cacheIotBoxRecords,
            get status() {
                return iotHttp.connectionStatus;
            },
        };
    },
};

registry.category("services").add("iot_http", iotHttpService);
