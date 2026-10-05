import { Dialog } from "@web/core/dialog/dialog";
import { Component, useProps, t } from "@odoo/owl";
import { BadgeTag } from "@web/core/tags_list/badge_tag";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { _t } from "@web/core/l10n/translation";
import { getTime } from "@pos_urban_piper/utils";

const STATES = {
    draft: { label: _t("New"), color: 2 },
    paid: { label: _t("Paid"), color: 4 },
    done: { label: _t("Posted"), color: 10 },
    cancel: { label: _t("Cancelled"), color: 9 },
};

export class OrderInfoPopup extends Component {
    static components = { Dialog, BadgeTag };
    static template = "pos_urban_piper.OrderInfoPopup";
    props = useProps({
        order: t.instanceOf(PosOrder),
        close: t.function(),
        previousOrderCount: t.number(),
    });

    setup() {
        this.pos = usePos();
        this.order = this.props.order;
        this.states = STATES;
        this.deliveryJson = this.order.deliveryJson;
        this.extPlatform = this.order.extPlatform;
        this.deliveryRiderJson = JSON.parse(this.order.delivery_rider_json || "{}");
        this.payment_option_display = {
            prepaid: _t("Prepaid"),
            payment_gateway: _t("Payment Gateway"),
            cash: _t("Cash"),
            card_on_delivery: _t("Card on Delivery"),
            paytm: _t("Paytm"),
            wallet_credit: _t("Wallet Credit"),
            simpl: _t("Simpl (Deferred Payment)"),
            aggregator: _t("Aggregator (Handled by Platform)"),
        };
        this.orderDetails = this.getOrderDetails();
        this.cardsData = [this.orderInfo, this.customerInfo, this.deliveryPersonData];
    }

    get title() {
        return _t("Order Details: ") + this.order.getName();
    }

    get provider() {
        return this.order.delivery_provider_id;
    }

    get deliveryPersonData() {
        return {
            title: _t("Rider Info"),
            icon: "two_wheeler",
            visible: Boolean(this.order.delivery_rider_json),
            fields: [
                {
                    label: _t("Rider Name"),
                    value: this.deliveryRiderJson.delivery_person_details?.name,
                },
                {
                    label: _t("Rider Phone"),
                    value: this.deliveryRiderJson.delivery_person_details?.phone,
                    link: `tel:${this.deliveryRiderJson.delivery_person_details?.phone}`,
                },
                {
                    label: _t("Status"),
                    value: this.deliveryRiderJson.status_updates?.[
                        this.deliveryRiderJson.status_updates.length - 1
                    ]?.status,
                },
            ],
        };
    }

    get customerInfo() {
        const deliveryCustomerData = this.order.deliveryCustomerData;
        return {
            title: _t("Customer Info"),
            icon: "person",
            visible: true,
            fields: [
                { label: _t("Customer Name"), value: deliveryCustomerData.name },
                { label: _t("Delivery Address"), value: deliveryCustomerData.address },
                {
                    label: _t("Customer Phone"),
                    value: deliveryCustomerData.phone,
                    link: `tel:${deliveryCustomerData.phone}`,
                },
                {
                    label: _t("Email"),
                    value: deliveryCustomerData.email,
                    link: `mailto:${deliveryCustomerData.email}`,
                },
            ],
            subTitleValue: this.props.previousOrderCount
                ? _t("- %s Previous Order(s)", this.props.previousOrderCount)
                : false,
        };
    }

    get orderInfo() {
        return {
            title: _t("Order Info"),
            icon: "bookmark",
            iconClass: "oi-filled",
            visible: true,
            fields: [
                {
                    label: _t("Status"),
                    value: this.order.deliveryStatusStr,
                },
                { label: _t("Fulfilment Mode"), value: this.orderDetails.fulfilmentMode },
                {
                    label: _t("Channel"),
                    value: `${this.order.delivery_provider_id?.name} - ${this.orderDetails.channelOtp}`,
                },
                {
                    label: _t("Location"),
                    value: this.pos.config.name,
                },
                { label: _t("Payment Mode"), value: this.orderDetails.paymentMode },
                {
                    label: _t("Order Time"),
                    value: getTime(this.deliveryJson.order?.details?.created),
                },
                {
                    label: _t("Delivery Time"),
                    value: getTime(this.deliveryJson.order?.details?.delivery_datetime),
                },
                { label: _t("Order ID"), value: this.order.delivery_identifier },
                ...this.providerFieldsInfo,
            ],
        };
    }

    get providerFieldsInfo() {
        const deliveryProvider = this.provider?.technical_name;
        let orderInfoFields = [];
        if (this.orderDetails.orderOtp) {
            orderInfoFields.push({ label: _t("Order OTP"), value: this.orderDetails.orderOtp });
        }
        if (deliveryProvider === "talabat") {
            orderInfoFields = [
                {
                    label: _t("Talabat Code"),
                    value: this.orderDetails.talabatCode,
                },
                {
                    label: _t("Talabat Short Code"),
                    value: this.orderDetails.talabatShortCode,
                },
            ];
        }
        if (deliveryProvider === "hungerstation") {
            orderInfoFields.push({
                label: _t("HungerStation Code"),
                value: this.orderDetails.hungerstationCode,
            });
        }
        if (deliveryProvider === "ubereats") {
            orderInfoFields = [
                ...orderInfoFields,
                {
                    label: _t("Contact Access Code"),
                    value: this.orderDetails.accessCode || "",
                },
                {
                    label: _t("Rider Mask Code"),
                    value: this.orderDetails.riderMaskCode || "",
                },
            ];
        }
        return orderInfoFields;
    }

    getOrderDetails() {
        const orderDetails = {
            channelOtp: this.extPlatform.id,
            orderOtp: this.extPlatform.extras?.order_otp,
            fulfilmentMode: this.extPlatform.delivery_type,
            paymentMode:
                this.deliveryJson.order?.payment
                    ?.map(
                        (payment) => this.payment_option_display[payment.option] || payment.option
                    )
                    ?.join(", ") || _t("Not Specified"),
        };
        const deliveryProvider = this.provider?.technical_name;
        if (deliveryProvider === "talabat") {
            orderDetails["talabatCode"] = this.extPlatform.extras?.talabat_code;
            orderDetails["talabatShortCode"] = this.extPlatform.extras?.talabat_shortcode;
        }
        if (deliveryProvider === "hungerstation") {
            orderDetails["hungerstationCode"] = this.extPlatform.extras?.hungerstation_code;
        }
        if (deliveryProvider === "ubereats") {
            orderDetails["riderMaskCode"] = this.extPlatform.extras?.ubereats_rider_mask_code;
            orderDetails["accessCode"] = this.extPlatform.extras?.contact_access_code;
        }
        return orderDetails;
    }

    onClose() {
        this.props.close();
    }
}
