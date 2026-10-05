import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { PaymentInterfaceIot } from "@pos_iot/app/utils/payment/payment_interface_iot";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class PaymentSix extends PaymentInterfaceIot {
    getPaymentData(uuid) {
        const paymentLine = this.pos.getOrder().getPaymentlineByUuid(uuid);
        return {
            messageType: "Transaction",
            transactionType: paymentLine.amount >= 0 ? "Payment" : "Refund",
            amount: Math.abs(Math.round(paymentLine.amount * 100)),
            currency: this.pos.currency.name,
            cid: uuid,
            posId: this.pos.session.id,
            userId: this.pos.user?.id || 2,
        };
    }

    getCancelData(uuid) {
        return {
            messageType: "Cancel",
            cid: uuid,
        };
    }

    getPaymentLineForMessage(order, data) {
        const line = order.getPaymentlineByUuid(data.cid);
        const terminalProxy = line?.payment_method_id.iot_device_id;
        if (line && terminalProxy) {
            return line;
        }
        return null;
    }

    onTerminalMessageReceived(data, line) {
        if (data.Stage === "Cancel") {
            // Result of a cancel request
            if (data.Error) {
                this._resolveCancellation?.(false);
                this.env.services.dialog.add(AlertDialog, {
                    title: _t("Transaction could not be cancelled"),
                    body: data.Error,
                });
            } else {
                this._resolveCancellation?.(true);
                this._resolvePayment?.(false);
            }
        } else if (data.Disconnected) {
            // Terminal disconnected
            line.setPaymentStatus("force_done");
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Terminal Disconnected"),
                body: _t(
                    "Please check the network connection and then check the status of the last transaction manually."
                ),
            });
        } else if (line.payment_status !== "retry") {
            // Result of a transaction
            if (data.Error) {
                this.env.services.dialog.add(AlertDialog, {
                    title: _t("Payment terminal error"),
                    body: _t(data.Error),
                });
                this._resolvePayment?.(false);
            } else if (data.Response === "Approved") {
                if (data.Card) {
                    line.card_type = data.Card;
                }
                this._resolvePayment?.(true);
            }
        }
    }

    _onBalanceComplete(data) {
        if (data.Error || !data.Ticket) {
            const error_msg =
                data.Error && data.Error !== ""
                    ? data.Error
                    : _t("Failed to get balance report from the terminal. Please retry.");
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Six balance report error"),
                body: error_msg,
            });
            return;
        }
        const printer = this.pos.ticketPrinter;
        if (printer.defaultPrinter) {
            printer
                .generateIframe("pos_iot_six.pos_six_balance_receipt", {
                    lines: data.Ticket.split("\n"),
                })
                .then((iframe) => printer.printWithFallback({ iframe }));
        }
    }

    async sendBalance() {
        if (!this.terminal) {
            this._showErrorConfig();
            return false;
        }
        const printer =
            this.pos.ticketPrinter.defaultPrinter || (await this.pos.ticketPrinter.selectPrinter());
        if (!printer) {
            this.env.services.dialog.add(AlertDialog, {
                title: _t("No printer configured"),
                body: _t(
                    "You must select a printer in your POS config to print Six balance report"
                ),
            });
            return false;
        }
        const data = {
            messageType: "Balance",
            posId: this.pos.session.id,
            userId: this.pos.session.user_id.id,
        };

        return this.pos.iotHttp.action(
            this.terminal.iot_id,
            this.terminal.identifier,
            data,
            (e) => this._onBalanceComplete(e.result),
            (e) => this._onBalanceComplete(e)
        );
    }
}

registry.category("pos_payment_providers").add("six_iot", PaymentSix);
