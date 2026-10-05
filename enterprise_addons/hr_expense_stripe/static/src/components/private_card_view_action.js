/* global Stripe */
import { Component, onWillStart, proxy, signal, t, useProps } from "@odoo/owl";
import { cookie } from "@web/core/browser/cookie";
import { Dialog } from "@web/core/dialog/dialog";
import { WarningDialog } from "@web/core/errors/error_dialogs";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useLayoutEffect } from "@web/owl2/utils";
import { InputVerificationCode } from "./verification_code_input";

class PrivateCardViewDialog extends Component {
    static template = "hr_expense_stripe.privateCardViewDialog";
    static components = { Dialog, InputVerificationCode };

    props = useProps({
        action: t.object(),
        close: t.function(),
    });

    numberPlaceholderRef = signal.ref();
    cvcPlaceholderRef = signal.ref();
    numberCopyPlaceholderRef = signal.ref();
    cvcCopyPlaceholderRef = signal.ref();
    pinPlaceholderRef = signal.ref();

    setup() {
        this.card_id = this.props.action.params.res_id;
        this.stripe_id = this.props.action.params.stripe_id;

        this.dialog = useService("dialog");
        this.ui = useService("ui");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = proxy({
            ephemeralKey: undefined,
            nonce: undefined,
            session: undefined,
            message: _t("Enter the code we sent to the cardholder's phone or email: Fetching ..."),
            card: {
                name: _t("Cardholder Name"),
                number: "**** **** **** 1234",
                type: _t("Virtual"),
                card_type: "virtual",
                exp: "12/29",
                cvc: "***"
            }
        });

        this.close = this.props.close;

        useLayoutEffect(
            (ephemeralKey) => {
                if (ephemeralKey)
                    this.buildStripeIframes();
            },
            () => [this.state.ephemeralKey]
        );

        onWillStart(async () => {
            await this.initStripeJS();
            this.send2FARequest();
        })
    }
    // Common
    async initStripeJS() {
        const result = await this.ormCardCall("get_stripe_js_init_params");
        if(!result) {
            this.raiseUIError(_t("Failed to fetch StripeJS initialization params."));
        }

        this.stripejs = Stripe(result.public_key, {
            stripeAccount: result.account
        });
    }

    // Card View
    async fetchCardInfo() {
        try {
            let result = (await this.orm.read(
                "hr.expense.stripe.card",
                [this.card_id],
                [
                    "name",
                    "card_number_public",
                    "card_type",
                    "expiration"
                ]
            ))[0];

            this.state.card.name = result.name;
            this.state.card.exp = result.expiration;
            this.state.card.number = result.card_number_public;
            this.state.card.type = result.card_type === "virtual" ? _t("Virtual") : _t("Physical");
            this.state.card.card_type = result.card_type;
        }
        catch (error) {
            this.close();
            throw error;
        }
    }

    async buildStripeIframes() {
        const elements = this.stripejs.elements();
        let cardNumberElement = elements.create(
            "issuingCardNumberDisplay",
            {
                issuingCard: this.stripe_id,
                nonce: this.state.nonce,
                ephemeralKeySecret: this.state.ephemeralKey,
                style: {
                    base: {
                        color: '#fff',
                        fontWeight: 700,
                        fontSize: '16px',
                        alignSelf: 'center'
                    },
                }
            }
        );

        // Small Fix as sometimes when we click on the numbers it calls focus which is not available for issuing elements
        cardNumberElement.focus = () => {};
        cardNumberElement.mount(this.numberPlaceholderRef());

        let cardCvcElement = elements.create(
            "issuingCardCvcDisplay",
            {
                issuingCard: this.stripe_id,
                nonce: this.state.nonce,
                ephemeralKeySecret: this.state.ephemeralKey,
                style: {
                    base: {
                        color: '#fff',
                        fontWeight: 400,
                        fontSize: '14px',
                        alignSelf: 'center'
                    },
                }
            }
        );
        // Small Fix as sometimes when we click on the numbers it calls focus which is not available for issuing elements
        cardCvcElement.focus = () => {};
        cardCvcElement.mount(this.cvcPlaceholderRef());

        let cardPinElement = elements.create(
            "issuingCardPinDisplay",
            {
                issuingCard: this.stripe_id,
                nonce: this.state.nonce,
                ephemeralKeySecret: this.state.ephemeralKey,
                style: {
                    base: {
                        color: cookie.get("color_scheme") === "dark" ? '#fff' : '#000',
                        fontWeight: 400,
                        fontSize: '14px',
                        alignSelf: 'center'
                    },
                }
            }
        );
        // Small Fix as sometimes when we click on the numbers it calls focus which is not available for issuing elements
        cardPinElement.focus = () => {};
        cardPinElement.mount(this.pinPlaceholderRef());

        //Copy buttons
        let cardNumberCopyElement = elements.create(
            "issuingCardCopyButton",
            {
                toCopy: 'number',
                style: {
                    base: {
                        fontSize: '1.1rem',
                    },
                }
            }
        );
        cardNumberCopyElement.mount(this.numberCopyPlaceholderRef());
        cardNumberCopyElement.on('click', () => {
            this.notification.add(_t("Card number copied to the clipboard."), {
                type: "info",
            });
        })

        let cardCvcCopyElement = elements.create(
            "issuingCardCopyButton",
            {
                toCopy: 'cvc',
                style: {
                    base: {
                        fontSize: '0.9rem',
                    },
                }
            }
        );
        cardCvcCopyElement.mount(this.cvcCopyPlaceholderRef());
        cardCvcCopyElement.on('click', () => {
            this.notification.add(_t("Card cvc copied to the clipboard."), {
                type: "info",
            });
        })
    }

    // 2FA
    async send2FARequest() {
        const phoneResult = await this.ormCardCall("action_send_iap_2fa_code");
        this.state.session = phoneResult.session_id;
        if (phoneResult.phone_number_last3) {
            this.state.message = _t(
                "Enter the code we sent to the cardholder's phone number ending in %(phone)s.",
                { phone: phoneResult.phone_number_last3 },
            );
        } else if (phoneResult.sanitized_email) {
            this.state.message = _t(
                "Enter the code we sent to the cardholder's email %(email)s.",
                { email: phoneResult.sanitized_email },
            );
        }
    }

    async requestEphemeralKey(code) {
        const nonceResult = await this.stripejs.createEphemeralKeyNonce({
            issuingCard: this.stripe_id
        });
        this.ui.unblock();
        this.state.nonce = nonceResult.nonce;
        const ephemeralKeyResult = await this.ormCardCall(
            "action_request_ephemeral_key",
            nonceResult.nonce,
            code,
            this.state.session
        );
        if (ephemeralKeyResult) {
            await this.fetchCardInfo();
            this.state.ephemeralKey = ephemeralKeyResult.secret;
        }
    }

    // Utility functions
    ormCardCall(functionName, ...params) {
        try {
            return this.orm.call(
                "hr.expense.stripe.card",
                functionName,
                [
                    this.card_id,  // res_id
                    ...params
                ]
            )
        }
        catch (error) {
            this.close();
            throw error;
        }
    }

    raiseUIError(message) {
        this.dialog.add(WarningDialog, {
            title: _t("Error"),
            message: message,
        });
        this.close();
    }
}

export function PrivateCardViewAction(env, action) {
    const dialog = useService("dialog");
    return new Promise((resolve) => {
        dialog.add(
            PrivateCardViewDialog,
            { action },
            {
                onClose: () => {
                    resolve({ type: "ir.actions.act_window_close" });
                },
            }
        );
    });
}

registry.category("actions")
    .add("hr_expense_stripe.private_card_view_action", PrivateCardViewAction);
