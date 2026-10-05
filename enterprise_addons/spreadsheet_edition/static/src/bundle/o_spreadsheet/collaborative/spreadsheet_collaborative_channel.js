import { ConnectionLostError, rpc } from "@web/core/network/rpc";
import { ClientDisconnectedError } from "@odoo/o-spreadsheet";
import { debounce } from "@web/core/utils/timing";

const DEBOUNCE_TIME = 200;

/**
 * This class implements the `TransportService` interface defined
 * by o-spreadsheet. Its purpose is to communicate with other clients
 * by sending and receiving spreadsheet messages through the server.
 * @see https://github.com/odoo/o-spreadsheet
 *
 * It listens messages on the long polling bus and forwards spreadsheet messages
 * to the handler. (note: it is assumed there is only one handler)
 *
 * It uses the RPC protocol to send messages to the server which
 * push them in the long polling bus for other clients.
 */
export class SpreadsheetCollaborativeChannel {
    static dependencies = ["bus_service", "orm"];

    /**
     * @param {Env} env
     * @param {string} resModel model linked to the spreadsheet
     * @param {number} resId Id of the spreadsheet
     * @param {number} [shareId]
     * @param {string} [accessToken] sharing token
     */
    constructor(env, resModel, resId, shareId, accessToken) {
        this.env = env;
        this.resId = resId;
        this.resModel = resModel;
        this.shareId = shareId;
        this.accessToken = accessToken;
        /**
         * A callback function called to handle messages when they are received.
         */
        this._listener;
        /**
         * Messages are queued while there is no listener. They are forwarded
         * once it registers.
         */
        this._queue = [];
        this._channel = this._getChannel();
        this.env.services.bus_service.addChannel(this._channel);
        this.env.services.bus_service.subscribe("spreadsheet", (payload) => {
            if (payload.id === this.resId) {
                this._handleNotification(payload);
            }
        });
        this._debouncedSendMessage = debounce(this._sendMessage.bind(this), DEBOUNCE_TIME);
    }

    /**
     * Register a function that is called whenever a new spreadsheet revision
     * message notification is received by server.
     *
     * @param {any} id
     * @param {Function} callback
     */
    onNewMessage(id, callback) {
        this._listener = callback;
        for (const message of this._queue) {
            callback(message);
        }
        this._queue = [];
    }

    /**
     * Send a message to the server
     *
     * @param {Object} message
     */
    async sendMessage(message) {
        if (message.type === "CLIENT_MOVED" || message.type === "CLIENT_JOINED") {
            return this._debouncedSendMessage(message);
        } else {
            return this._sendMessage(message);
        }
    }

    async _sendMessage(message) {
        let isAccepted = false;
        try {
            const result = await rpc(
                `/spreadsheet/${this.resModel}/${this.resId}/dispatch`,
                {
                    message,
                    access_token: this.accessToken,
                },
                { silent: true }
            );
            isAccepted = result?.accepted;
        } catch (e) {
            if (e instanceof ConnectionLostError) {
                throw new ClientDisconnectedError("", { cause: e });
            }
            throw e;
        } finally {
            if (isAccepted) {
                this._handleNotification(message);
            }
        }
    }

    /**
     * Stop listening new messages
     */
    leave() {
        this._debouncedSendMessage.cancel();
        this._listener = undefined;
    }

    /**
     * Either forward the message to the listener if it's already registered,
     * or put it in a queue.
     *
     * @private
     * @param {Object} notifs
     */
    _handleNotification(payload) {
        if (!this._listener) {
            this._queue.push(payload);
        } else {
            this._listener(payload);
        }
    }

    /**
     * @private
     * @returns {string}
     */
    _getChannel() {
        // Listening this channel tells the server the spreadsheet is active
        // but the server will actually push to channel [{dbname},  {resModel}, {resId}]
        // The user can listen to this channel only if he has the required read access.
        const channel = `spreadsheet_collaborative_session:${this.resModel}:${this.resId}`;
        if (this.accessToken) {
            return `${channel}:${this.shareId ?? 0}:${this.accessToken}`;
        }
        return channel;
    }
}
