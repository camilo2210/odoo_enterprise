/* global TYRO */

import { loadJS } from "@web/core/assets";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { registry } from "@web/core/registry";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { TYRO_LIB_URLS } from "@pos_tyro/urls";
import { FailureDialog } from "@pos_tyro/app/components/failure_dialog";
import { QuestionDialog } from "@pos_tyro/app/components/question_dialog";
import { _t } from "@web/core/l10n/translation";

export class PaymentTyro extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.dialog = this.env.services.dialog;
        this.currentQuestion = null;
        this.loadTyroClient();
    }

    async loadTyroClient() {
        await loadJS(TYRO_LIB_URLS[this.payment_method_id.tyro_mode]);
        const posProductInfo = await this.callPaymentMethod("get_tyro_product_info", [
            this.payment_method_id.id,
        ]);
        this.tyroClient = new TYRO.IClient(posProductInfo.apiKey, posProductInfo);

        if (
            this.paymentLine?.payment_method_id === this.payment_method_id &&
            ["waitingCard", "waitingCancel"].includes(this.paymentLine.payment_status)
        ) {
            this.resumePayment();
        }
    }

    get paymentLine() {
        return this.pos.getOrder()?.getSelectedPaymentline();
    }

    async addTip(tip) {
        if (this.pos.config.self_ordering_mode === "kiosk") {
            this._showError("Tips/surcharges are not supported in the kiosk.");
            return;
        }
        const tipAmount = parseInt(tip, 10) / 100;
        if (!this.pos.config.tip_product_id || !this.pos.config.iface_tipproduct) {
            await this.pos.addTyroSurcharge(
                tipAmount,
                this.payment_method_id.tyro_surcharge_product_id
            );
            this._showError(
                _t(
                    "A tip was added on the Tyro terminal, but tipping is not enabled for this Point of Sale. It will instead be recorded as a surcharge."
                ),
                _t("Tyro Warning")
            );
        } else {
            const tipProduct = this.pos.config.tip_product_id;
            const orderLines = this.pos.getOrder().lines;
            const existingTip = orderLines.find((line) => line.product_id.id === tipProduct.id);
            await this.pos.setTip(tipAmount + (existingTip?.price_unit ?? 0));
        }
        this.paymentLine.setAmount(this.paymentLine.amount + tipAmount);
    }

    async addSurcharge(surcharge) {
        const surchargeAmount = parseFloat(surcharge);
        await this.pos.addTyroSurcharge(
            surchargeAmount,
            this.payment_method_id.tyro_surcharge_product_id
        );
        this.paymentLine.setAmount(this.paymentLine.amount + surchargeAmount);
    }

    async onTransactionComplete(response, resultCallback) {
        const line = this.paymentLine;
        this.dialog.closeAll();
        this.currentQuestion = null;

        if (response.result === "APPROVED") {
            line.transaction_id = response.transactionId;
            line.payment_ref_no = response.transactionReference;
            line.payment_method_authcode = response.authorisationCode;
            line.card_type = response.cardType;
            line.card_no = response.elidedPan;
            if (response.tipAmount) {
                await this.addTip(response.tipAmount);
            }
            if (response.surchargeAmount && response.surchargeAmount !== "0.00") {
                await this.addSurcharge(response.surchargeAmount);
            }
            resultCallback(true);
        } else {
            if (response.result !== "CANCELLED" || response.customerReceipt) {
                this.dialog.add(FailureDialog, {
                    result: response.result,
                    hasReceipt: !!response.customerReceipt,
                    printReceipt: () =>
                        this.pos.ticketPrinter.printReceipt({ printBillActionTriggered: true }),
                });
            }
            resultCallback(false);
        }
        this.printMerchantReceipt();
    }

    onMerchantReceiptReceived(response) {
        if (
            response.signatureRequired ||
            this.payment_method_id.tyro_always_print_merchant_receipt
        ) {
            this.paymentLine.tyro_merchant_receipt = response.merchantReceipt;
            if (response.signatureRequired) {
                this.printMerchantReceipt();
            }
        }
    }

    printMerchantReceipt() {
        if (!this.pos.ticketPrinter.receiptPrinters.length) {
            console.warn("Attempted to print merchant receipt from kiosk, ignoring.");
            return;
        }
        if (this.paymentLine.tyro_merchant_receipt) {
            this.pos
                .printReceipt({
                    printBillActionTriggered: true,
                })
                .then(() => {
                    this.paymentLine.tyro_merchant_receipt = null;
                });
        }
    }

    onQuestionReceived(question, answerCallback) {
        // Tyro re-sends the question every so often, so
        // we do nothing if we are already displaying the
        // question.
        if (this.currentQuestion === question.text) {
            return;
        }
        this.currentQuestion = question.text;
        const onClickAnswer = (answer) => {
            this.currentQuestion = null;
            answerCallback(answer);
        };
        this.dialog.add(QuestionDialog, {
            question,
            onClickAnswer,
        });
    }

    validateRefundAmount() {
        const order = this.pos.getOrder();
        const totalAmount = order.totalDue;
        const amountDue = order.remainingDue;
        const line = order.getSelectedPaymentline();
        if (totalAmount < 0 && amountDue > line.amount) {
            this._showError(_t("You cannot refund more than the original amount."));
            return false;
        }
        return true;
    }

    resumePayment() {
        const line = this.paymentLine;
        const resolve = (success) => {
            if (success) {
                line.setPaymentStatus("done");
            } else {
                line.setPaymentStatus("retry");
            }
        };
        const requestCallbacks = {
            receiptCallback: this.onMerchantReceiptReceived.bind(this),
            questionCallback: this.onQuestionReceived.bind(this),
            statusMessageCallback: (response) => {
                line.tyro_status = response;
            },
            transactionCompleteCallback: (response) =>
                this.onTransactionComplete(response, resolve),
        };
        if (line.payment_status === "waitingCancel") {
            line.setPaymentStatus("waitingCard");
        }
        this.tyroClient.continueLastTransaction(requestCallbacks);
    }

    async sendPaymentRequest(line) {
        /**
         * Override
         */
        await super.sendPaymentRequest(...arguments);
        try {
            line.setPaymentStatus("waitingCard");
            line.tyro_status = "Initiating...";

            return new Promise((resolve) => {
                const requestArguments = {
                    amount: Math.abs(Math.round(line.amount * 100)).toString(10),
                    mid: this.payment_method_id.tyro_merchant_id,
                    tid: this.payment_method_id.tyro_terminal_id,
                    integrationKey: this.payment_method_id.tyro_integration_key,
                    integratedReceipt: this.payment_method_id.tyro_integrated_receipts,
                };
                const requestCallbacks = {
                    receiptCallback: this.onMerchantReceiptReceived.bind(this),
                    questionCallback: this.onQuestionReceived.bind(this),
                    statusMessageCallback: (response) => {
                        line.tyro_status = response;
                    },
                    transactionCompleteCallback: (response) =>
                        this.onTransactionComplete(response, resolve),
                };

                if (line.amount < 0) {
                    if (this.validateRefundAmount()) {
                        this.tyroClient.initiateRefund(requestArguments, requestCallbacks);
                    } else {
                        resolve(false);
                    }
                } else {
                    this.tyroClient.initiatePurchase(
                        { ...requestArguments, enableSurcharge: true },
                        requestCallbacks
                    );
                }
            });
        } catch (error) {
            this._showError(error.message);
            return false;
        }
    }

    async sendPaymentCancel(line) {
        /**
         * Override
         */
        await super.sendPaymentCancel(...arguments);

        try {
            this.tyroClient.cancelCurrentTransaction();
        } catch (error) {
            this._showError(error.message);
            return true;
        }
    }

    _showError(msg, title) {
        if (!title) {
            title = _t("Tyro Error");
        }
        this.dialog.add(AlertDialog, {
            title: title,
            body: msg,
        });
    }
}

registry.category("pos_payment_providers").add("tyro", PaymentTyro);
