import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { user } from "@web/core/user";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";

class JournalCreateWizardCard extends Component {
    static template = "account.JournalCreateWizardCard";

    props = useProps({
        images: t.any(),
        title: t.any(),
        text: t.any(),
    });
}

export class JournalCreateWizard extends Component {
    static template = "account.JournalCreateWizard";
    static components = { JournalCreateWizardCard };

    props = useProps(standardActionServiceProps);

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");

        // Setup keyboard navigation
        useHotkey("arrowdown", () => this.navigateVertical("next"), { bypassEditableProtection: true, allowRepeat: true });
        useHotkey("arrowup", () => this.navigateVertical("previous"), { bypassEditableProtection: true, allowRepeat: true });
        useHotkey("arrowright", () => this.navigateHorizontal("next"), { bypassEditableProtection: true, allowRepeat: true });
        useHotkey("arrowleft", () => this.navigateHorizontal("previous"), { bypassEditableProtection: true, allowRepeat: true });
        useHotkey("enter", () => this.activateFocusedElement(), { bypassEditableProtection: true });

        onWillStart(async () => {
            this.hasGroupAccountUser = await user.hasGroup("account.group_account_user");
        });
    }

    async openAccountWizard(type) {
        const addBankAction = await this.orm.call(
            "res.company",
            `setting_init_${type}_account_action`,
            user.activeCompany.ids
        );
        this.action.doAction(addBankAction);
        this.env.dialogData.close();
    }

    openCreateJournalForm(type) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.journal",
            views: [[false, "form"]],
            target: "current",
            context: { default_type: type },
        });
    }

    cardImages(cardType) {
        const result = cardType === "card" ? ["logo_visa", "logo_mastercard"] : [cardType];
        return result.map((imageName) => `/account_accountant/static/src/img/journal_create_wizard/${imageName}.svg`);
    }

    get cardsData() {
        const data = [
            {
                images: this.cardImages("bank"),
                title: _t("Bank"),
                text: _t("Connect your bank and payment gateways (Paypal, Stripe, ...) or record your transactions manually"),
                onClick: () => this.openAccountWizard("bank"),
            },
            {
                images: this.cardImages("card"),
                title: _t("Card"),
                text: _t("Connect your credit card accounts and manage your payouts"),
                onClick: () => this.openAccountWizard("credit_card"),
            },
            {
                images: this.cardImages("cash"),
                title: _t("Cash"),
                text: _t("Record your cash movements and transfers"),
                onClick: () => this.openCreateJournalForm("cash"),
            },
        ];

        if (this.hasGroupAccountUser) {
            data.push(
                {
                    images: this.cardImages("general"),
                    title: _t("Miscellaneous Journal"),
                    text: _t("Payroll, depreciation, closing entries, deferred revenues, ...etc"),
                    onClick: () => this.openCreateJournalForm("general"),
                },
                {
                    images: this.cardImages("sale"),
                    title: _t("Sales Journal"),
                    text: _t("Create a separate journal for specific sales activities"),
                    onClick: () => this.openCreateJournalForm("sale"),
                },
                {
                    images: this.cardImages("purchase"),
                    title: _t("Purchases Journal"),
                    text: _t("Create a separate journal to organize vendor bills"),
                    onClick: () => this.openCreateJournalForm("purchase"),
                }
            );
        }

        return data;
    }

    /**
     * Get all navigable elements within the wizard container
     */
    getNavigableElements() {
        const container = document.querySelector(".journal-create-wizard-card")?.closest(".container");
        if (!container) {
            return [];
        }
        return Array.from(container.querySelectorAll(".o-navigable"));
    }

    /**
     * Group navigable elements into rows based on their vertical position.
     * Returns an array of rows, each row being an array of elements.
     */
    getElementRows(elements) {
        const rows = [];
        for (const el of elements) {
            const top = el.getBoundingClientRect().top;
            const existingRow = rows.find((row) => Math.abs(row[0].getBoundingClientRect().top - top) < 2);
            if (existingRow) {
                existingRow.push(el);
            } else {
                rows.push([el]);
            }
        }
        return rows;
    }

    navigateVertical(direction) {
        const elements = this.getNavigableElements();
        if (elements.length === 0) {
            return;
        }

        const activeElement = document.activeElement;
        const rows = this.getElementRows(elements);
        const rowIndex = rows.findIndex((row) => row.includes(activeElement));

        if (rowIndex === -1) {
            elements[0]?.focus();
            return;
        }

        const colIndex = rows[rowIndex].indexOf(activeElement);
        const targetRowIndex = direction === "next"
            ? Math.min(rowIndex + 1, rows.length - 1)
            : Math.max(rowIndex - 1, 0);
        const targetRow = rows[targetRowIndex];
        // Use the same column, clamped to the target row's length
        targetRow[Math.min(colIndex, targetRow.length - 1)]?.focus();
    }

    navigateHorizontal(direction) {
        const elements = this.getNavigableElements();
        if (elements.length === 0) {
            return;
        }

        const activeElement = document.activeElement;
        const rows = this.getElementRows(elements);
        const currentRow = rows.find((row) => row.includes(activeElement));

        if (!currentRow) {
            elements[0]?.focus();
            return;
        }

        const colIndex = currentRow.indexOf(activeElement);
        const targetIndex = direction === "next"
            ? Math.min(colIndex + 1, currentRow.length - 1)
            : Math.max(colIndex - 1, 0);
        currentRow[targetIndex]?.focus();
    }

    /**
     * Activate (click) the currently focused element
     */
    activateFocusedElement() {
        const activeElement = document.activeElement;
        if (activeElement.classList.contains("o-navigable")) {
            activeElement.click();
        }
    }
}

registry.category("actions").add("journal_create_wizard", JournalCreateWizard);
