import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class PaymentInterfaceIot extends PaymentInterface {
    get terminal() {
        return this.payment_method_id.iot_device_id;
    }

    /**
     * Returns the data that will be sent to the payment terminal
     * upon initiating a payment.
     *
     * @param {string} uuid
     * The uuid of the payment line
     * @returns {object}
     * The data to send to the payment terminal
     */
    getPaymentData(uuid) {}

    /**
     * Returns the data that will be sent to the payment terminal
     * upon cancelling a payment.
     *
     * @param {string} uuid
     * The uuid of the payment line
     * @returns {object}
     * The data to send to the payment terminal
     */
    getCancelData(uuid) {}

    /**
     * Given a message received from the terminal, returns
     * the payment line to be processed.
     *
     * @param {PosOrder} order
     * The current order.
     * @param {object} data
     * The message received from the terminal.
     * @returns {PosPayment | null}
     * Returns the payment line if it is found and should
     * be processed, otherwise returns `null`, ignoring the
     * terminal message.
     */
    getPaymentLineForMessage(order, data) {}

    /**
     * Called whenever we receive a message from the terminal
     * after initiating a payment.
     * The method should call:
     * - `this._resolvePayment(true)` for a successful payment
     * - `this._resolvePayment(false)` for a failed payment
     * - `this._resolveCancellation(true)` for cancellation
     * - `this._resolveCancellation(false)` for failed cancellation
     * @param {object} data
     * The message data received from the terminal.
     * @param {PosPayment} line
     * The payment line for the terminal payment.
     */
    onTerminalMessageReceived(data, line) {}

    sendPaymentRequest(line) {
        super.sendPaymentRequest(...arguments);
        return this._sendTerminalRequest(this.getPaymentData(line.uuid), false);
    }

    sendPaymentCancel(line) {
        super.sendPaymentCancel(...arguments);
        return this._sendTerminalRequest(this.getCancelData(line.uuid), true);
    }

    _sendTerminalRequest(data, isCancellation) {
        if (!this.terminal) {
            this._showErrorConfig();
            return Promise.resolve(false);
        }

        return new Promise((resolve) => {
            const resolveRequest = (result) => {
                resolve(result);
                if (isCancellation) {
                    this._resolveCancellation = null;
                } else {
                    this._resolvePayment = null;
                }
                if (!this._resolveCancellation && !this._resolvePayment) {
                    this.transactionInProgress = false;
                }
            };
            if (isCancellation) {
                this._resolveCancellation = resolveRequest;
            } else {
                this._resolvePayment = resolveRequest;
            }

            this.transactionInProgress = true;
            this.pos.iotHttp.action(
                this.terminal.iot_id,
                this.terminal.identifier,
                data,
                (e) => this._onValueChange(this.pos.getOrder(), e.result),
                (e) => this._onActionFail(e)
            );
        });
    }

    _keepListening() {
        if (this.transactionInProgress) {
            this.pos.iotHttp.onMessage(
                this.terminal.iot_id,
                this.terminal.identifier,
                (e) => this._onValueChange(this.pos.getOrder(), e.result),
                (e) => this._onActionFail(e)
            );
        }
    }

    _onActionFail(data) {
        if (data.status === "timeout") {
            // ignore timeout, we keep waiting for the terminal to respond
            return this._keepListening();
        }
        this.transactionInProgress = false;
        this._resolvePayment?.(false);
        if (data?.Disconnected === "disconnected" || data.status === "disconnected") {
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Connection to terminal failed"),
                body: _t(
                    "The IoT Box cannot detect the payment terminal. Please check if the terminal is still connected."
                ),
            });
        }
    }

    _showErrorConfig() {
        this.env.services.dialog.add(AlertDialog, {
            title: _t("Configuration of payment terminal failed"),
            body: _t("Ensure a payment terminal is properly linked in the settings."),
        });
    }

    _onValueChange(order, data) {
        this._keepListening();
        const line = this.getPaymentLineForMessage(order, data);
        if (line && this.transactionInProgress) {
            this.onTerminalMessageReceived(data, line);
        }
    }
}
