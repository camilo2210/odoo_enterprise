import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.setAllTotalDueOfPartners(this.models["res.partner"].getAll());

        this.dummyProductForSettleStuff = this.models["product.template"].create({
            id: "dummy_product_for_settle_stuff",
            display_name: "Dummy Product for Settle Invoice",
            taxes_id: [],
        });
        this.models["product.product"].create({
            id: "dummy_product_for_settle_stuff_variant",
            product_tmpl_id: this.dummyProductForSettleStuff,
            display_name: "Dummy Product for Settle Invoice",
            name: "Dummy Product for Settle Invoice",
            taxes_id: [],
        });
    },
    get settleFields() {
        return ["total_due", "total_invoiced"];
    },
    async refreshTotalDueOfPartner(partner) {
        const readOnlyG = await user.hasGroup("account.group_account_readonly");
        const invoiceG = await user.hasGroup("account.group_account_invoice");
        if (!readOnlyG && !invoiceG) {
            return [];
        }

        const res = await this.data.read("res.partner", [partner.id], this.settleFields);
        this.deviceSync.dispatch({ "res.partner": [partner] });
        const updatePartner = res[0];
        if (partner.parent_name) {
            const parent = this.models["res.partner"].find((p) => p.name === partner.parent_name);
            if (parent) {
                partner = parent;
            }
        }
        return [updatePartner];
    },
    async setAllTotalDueOfPartners(partners) {
        const readOnlyG = await user.hasGroup("account.group_account_readonly");
        const invoiceG = await user.hasGroup("account.group_account_invoice");
        if (!readOnlyG && !invoiceG) {
            return;
        }

        await this.data.read(
            "res.partner",
            partners.map((p) => p.commercial_partner_id?.id || p.id),
            this.settleFields
        );
    },
    async selectPartner() {
        const order = this.getOrder();
        if (order?.uiState?.settlingInvoice) {
            await makeAwaitable(this.dialog, AlertDialog, {
                title: _t("Action not allowed"),
                body: _t("You cannot change the customer while settling invoices."),
            });
            return;
        }
        return await super.selectPartner(...arguments);
    },
    async deleteOrderAndGoToDefaultScreen(order) {
        const newOrder = this.createOrderIfNeeded();
        this.selectedOrderUuid = newOrder.uuid;
        const next = this.defaultPage;
        this.router.navigate(next.page, next.params);
        await this.refreshTotalDueOfPartner(order.partner_id);
        await this.deleteOrders([order]);
    },
    async onClickBackButton() {
        const order = this.getOrder();
        const settleActions = order?.uiState?.settlingInvoice || order?.uiState?.depositMoney;

        if (this.router.currentScreen() === "PaymentScreen" && settleActions) {
            const result = await makeAwaitable(this.dialog, AlertDialog, {
                title: _t("Cancel Settlement"),
                body: _t("Are you sure you want to cancel the settlement process?"),
            });

            if (result) {
                return await this.deleteOrderAndGoToDefaultScreen(order);
            }

            return false;
        }

        return super.onClickBackButton(...arguments);
    },
    async onClickSettleInvoices(invoiceIds, partnerId, commercialPartnerId) {
        const invoices = await this.data.read("account.move", invoiceIds);
        const currentOrder = this.getEmptyOrder();
        this.selectedOrderUuid = currentOrder.uuid;

        currentOrder.setPartner(partnerId);
        currentOrder.commercialPartnerId = commercialPartnerId;
        currentOrder.uiState.settlingInvoice = true;
        currentOrder.uiState.settledInvoiceIds = invoiceIds;

        for (const invoice of invoices) {
            const sign = invoice.move_type === "out_refund" ? -1 : 1;
            await this.addLineToCurrentOrder({
                qty: 1 * sign,
                price_unit: invoice.amount_residual,
                taxes_id: [],
                product_tmpl_id: this.dummyProductForSettleStuff,
            });
        }
        this.navigate("PaymentScreen", { orderUuid: currentOrder.uuid });
    },
    async onClickDepositMoney(amount, partnerId, commercialPartnerId) {
        const paymentMethod = this.config.paymentMethods.find(
            (method) => method.type !== "pay_later"
        );

        if (!paymentMethod) {
            return false;
        }

        const currentOrder = this.getEmptyOrder();
        currentOrder.setPartner(partnerId);
        currentOrder.commercialPartnerId = commercialPartnerId;
        currentOrder.uiState.depositMoney = true;
        currentOrder.uiState.is_settling_account = true;

        await this.addLineToCurrentOrder({
            qty: 1,
            price_unit: amount,
            taxes_id: [],
            product_tmpl_id: this.dummyProductForSettleStuff,
        });

        const { status, data: paymentLine } = currentOrder.addPaymentline(paymentMethod);
        if (!status) {
            return false;
        }

        paymentLine.setAmount(amount);
        this.navigate("PaymentScreen", {
            orderUuid: this.selectedOrderUuid,
        });

        return true;
    },
    async postSyncAllOrders(orders) {
        const paylaterPayments = orders
            .flatMap((order) => order.payment_ids)
            .filter((line) => line.payment_method_id?.type === "pay_later");

        if (paylaterPayments.length) {
            const partners = orders.map((order) => order.partner_id).filter(Boolean);
            await this.setAllTotalDueOfPartners(partners);
        }

        return await super.postSyncAllOrders(orders);
    },
    shouldSelectPreset(order) {
        return !order.uiState.is_settling_account && super.shouldSelectPreset(order);
    },
});
