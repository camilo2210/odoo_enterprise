import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PartnerList from "@point_of_sale/../tests/pos/tours/utils/partner_list_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import * as Utils from "@point_of_sale/../tests/pos/tours/utils/common";
import * as Settle from "@pos_settle_due/../tests/tours/utils";
import { negateStep } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_pos_settle_due_main", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            // Settle the backend created open invoice
            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("AAA - Moda", 200),
            PartnerList.clickPartnerOptions("AAA - Moda"),
            PartnerList.clickDropDownItemText("Settle invoices"),
            negateStep(PartnerList.checkDropDownItemText("Deposit money")),
            Settle.selectOrderToSettle("00001"),
            PaymentScreen.clickValidate(),
            ProductScreen.isShown(),

            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("AAA - Moda", false),
            negateStep(PartnerList.checkDropDownItemText("Settle invoices")),
            ProductScreen.clickCustomer("AAA - Moda"),
            ProductScreen.addOrderline("Desk Pad", "10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Customer Account"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            FeedbackScreen.checkTicketData({
                payment_lines: [
                    {
                        name: "Customer Account",
                        amount: "19.80",
                    },
                ],
            }),
            FeedbackScreen.clickNextOrder(),
            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("AAA - Moda", "19.80"),
            PartnerList.clickPartnerOptions("AAA - Moda"),
            PartnerList.clickDropDownItemText("Settle invoices"),
            Settle.selectOrderToSettle("00001"),
            PaymentScreen.clickValidate(),
            ProductScreen.isShown(),
            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("AAA - Moda", false),

            // Test money deposit
            PartnerList.clickPartnerOptions("AAA - Moda"),
            PartnerList.clickDropDownItemText("Deposit money"),
            PaymentScreen.enterPaymentLineAmount("Cash", "80000"),
            {
                trigger: `body button:contains('Validate'):not(.disabled)`,
                run: "click",
            },
            Dialog.confirm(),
            ProductScreen.isShown(),
            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("AAA - Moda", "80,000"),

            // Create a partially paid order
            ProductScreen.clickCustomer("AAA - Moda"),
            ProductScreen.addOrderline("Desk Pad", "10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.enterPaymentLineAmount("Cash", "10"),
            PaymentScreen.clickPaymentMethod("Customer Account"),
            PaymentScreen.clickValidate(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_settle_order_partially_backend_01", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("A Partner"),
            ProductScreen.addOrderline("Desk Pad", "10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Customer Account"),
            PaymentScreen.clickInvoiceButton(),
            PaymentScreen.clickValidate(),
            FeedbackScreen.clickNextOrder(),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount("A Partner", "19.80", "TSJ/", "/00001", true),
            ProductScreen.modeIsActive("Price"),
            ProductScreen.clickNumpad("1", "0"),
            ProductScreen.totalAmountIs("10.00"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Dialog.confirm("Yes"),
            FeedbackScreen.clickNextOrder(),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_settle_order_partially_backend_02", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.settleCustomerAccount("A Partner", "4.80", "TSJ/", "/00001", true),
            ProductScreen.totalAmountIs("4.80"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Dialog.confirm("Yes"),
            FeedbackScreen.clickNextOrder(),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_settle_due_search_more", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.searchCustomerValue("BPartner", true),
            {
                trigger: ".partner-line-balance:contains('10.00')",
            },
        ].flat(),
});

registry.category("web_tour.tours").add("pos_settle_open_invoice", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("C partner"),
            {
                isActive: ["auto"],
                trigger: "div.o_popover :contains('Settle invoices')",
                content: "Check the popover opened",
                run: "click",
            },
            {
                trigger: "tr.o_data_row td[name='name']:contains('INV/2025/00001')",
                content: "Check the invoice is present",
                run: "click",
            },
            ProductScreen.clickNumpad("5"),
            ProductScreen.selectedOrderlineHas("INV", 1, "5"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Utils.selectButton("Yes"),
            FeedbackScreen.isShown(),
            FeedbackScreen.checkTicketData({
                total_amount: "0.00",
                orderlines: [
                    {
                        name: "INV/2025/00001",
                        quantity: "0",
                        price_unit: "5.00",
                        line_price: "0.00",
                    },
                ],
                payment_lines: [
                    {
                        name: "Bank",
                        amount: "5.00",
                    },
                    {
                        name: "Customer Account",
                        amount: "-5.00",
                    },
                ],
            }),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("deposit_money_to_customer_and_pay_with_customer_account", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("A Partner"),
            PartnerList.clickDropDownItemText("Deposit money"),
            PaymentScreen.enterPaymentLineAmount("Cash", "100"),
            PaymentScreen.clickValidate(),
            Dialog.confirm(),
            ProductScreen.isShown(),
            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("A Partner", "100"),
            ProductScreen.clickCustomer("A Partner"),
            ProductScreen.addOrderline("Desk Pad", "1", "200"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Customer Account"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.clickNextOrder(),
            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("A Partner"),
            PartnerList.clickDropDownItemText("Settle invoices"),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("settle_partial_paid_invoice_from_pos", {
    steps: () =>
        [
            Chrome.startPoS(),
            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("A Partner", "100.00"),
            PartnerList.clickPartnerOptions("A Partner"),
            PartnerList.clickDropDownItemText("Settle invoices"),
            Settle.checkInvoicePaymentState("Partially Paid"),
            Settle.selectOrderToSettle("00001"),
            PaymentScreen.clickValidate(),
            ProductScreen.isShown(),
            ProductScreen.clickPartnerButton(),
            Settle.checkCustomerAmount("A Partner", false),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("pos_settle_open_invoice_with_credit_note", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            ProductScreen.clickPartnerButton(),
            PartnerList.clickPartnerOptions("C Partner"),
            {
                trigger: "div.o_popover :contains('Settle invoices')",
                content: "Open settle invoices from partner dropdown",
                run: "click",
            },
            {
                trigger: "thead .o_list_record_selector input",
                content: "Click 'Select All' checkbox to select both invoice and credit note",
                run: "click",
            },
            {
                trigger: "tr.o_data_row td[name='name']:contains('INV/2025/00001')",
                content: "Invoice is present in the settle dialog",
            },
            {
                trigger: "tr.o_data_row td[name='name']:contains('RINV/2025/00001')",
                content: "Credit note is present in the settle dialog",
            },
            {
                trigger: ".modal-footer button:contains('Select')",
                content: "Confirm selection of invoice and credit note",
                run: "click",
            },
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Chrome.endTour(),
        ].flat(),
});
