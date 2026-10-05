import { ActionMenus } from "@web/search/action_menus/action_menus";
import { BankRecButton } from "../button/button";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { useBankReconciliation } from "../bank_reconciliation_service";
import { _t } from "@web/core/l10n/translation";

export class BankRecControlPanel extends ControlPanel {
    static template = "account_accountant.BankRecControlPanel";
    static components = {
        ...ControlPanel.components,
        ActionMenus,
        BankRecButton,
        Dropdown,
        DropdownItem,
    };

    setup() {
        super.setup();
        this.ui = useService("ui");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.addDialog = useOwnedDialogs();
        this.bankReconciliation = useBankReconciliation();
    }

    /*
     * When selecting lines, you could have either both reconciled and unreconciled lines.
     * For reconciled lines: We send a notification to warn the user that the lines will stay untouched.
     * */
    sendAlreadyReconciledNotification() {
        if (this.selectedReconciledStatementLines.length) {
            this.notification.add(
                _t("Some lines cannot be processed because they have already been reconciled."),
                { type: "info" }
            );
        }
    }

    /*
     * When selecting lines, you could have either both validated and unvalidated lines.
     * For validated lines: We send a notification to warn the user that the lines will stay untouched.
     * */
    sendAlreadyValidatedNotification() {
        if (this.selectedUnvalidatedStatementLines.length != this.selectedStatementLines.length) {
            this.notification.add(
                _t(
                    "Some lines cannot be processed because they are already reconciled or cannot be validated."
                ),
                { type: "info" }
            );
        }
    }

    setPartnerOnReconcileLine() {
        // Send a notification for reconciled lines present in all the selected lines
        this.sendAlreadyReconciledNotification();
        const selectedLinesIds = this.selectedUnreconciledStatementLinesIds;
        if (!selectedLinesIds.length) {
            return;
        }

        const companyIds = [
            ...new Set(
                this.selectedUnreconciledStatementLines.map((st_line) => st_line.data.company_id.id)
            ),
        ];
        this.addDialog(SelectCreateDialog, {
            title: _t("Search: Partner"),
            noCreate: false,
            multiSelect: false,
            resModel: "res.partner",
            domain: [
                "|",
                ["company_id", "in", [false, ...companyIds]],
                ["company_id", "parent_of", companyIds],
            ],
            onSelected: async (partner) => {
                await this.orm.call(
                    "account.bank.statement.line",
                    "set_partner_bank_statement_line",
                    [selectedLinesIds, partner[0]]
                );
                let recordsToLoad = [];
                const partnerNames = this.selectedStatementLinesPartnerName;
                if (partnerNames) {
                    // Reload all impacted statement lines if we have a partner_name
                    recordsToLoad.push(
                        ...this.env.model.root.records.filter(
                            (record) =>
                                partnerNames.includes(record.data.partner_name) || record.selected
                        )
                    );
                } else {
                    recordsToLoad = this.recordsToReload;
                }
                await this.bankReconciliation.reloadRecords(recordsToLoad);
                await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
                    this.env.model.root.records
                );
                this.bankReconciliation.reloadChatter();
            },
        });
    }

    setAccountOnReconcileLine() {
        // Send a notification for reconciled lines present in all the selected lines
        this.sendAlreadyReconciledNotification();
        const selectedLinesIds = this.selectedUnreconciledStatementLinesIds;
        if (!selectedLinesIds.length) {
            return;
        }

        const suspenseLineIds = this.selectedUnreconciledStatementLines
            .map((st_line) => st_line.data.line_ids.records.at(-1))
            .map((line) => line.resId);

        const suspenseAccountIds = [
            ...new Set(
                this.selectedUnreconciledStatementLines.map(
                    (st_line) => st_line.data.journal_id.suspense_account_id.id
                )
            ),
        ];

        const defaultAccountIds = [
            ...new Set(
                this.selectedUnreconciledStatementLines.map(
                    (st_line) => st_line.data.journal_id.default_account_id.id
                )
            ),
        ];

        const context = {
            list_view_ref: "account_accountant.view_account_list_bank_rec_widget",
            search_view_ref: "account_accountant.view_account_search_bank_rec_widget",
        };

        this.addDialog(SelectCreateDialog, {
            title: _t("Search: Account"),
            noCreate: true,
            multiSelect: false,
            context: context,
            domain: [["id", "not in", [...suspenseAccountIds, ...defaultAccountIds]]],
            resModel: "account.account",
            onSelected: async (account) => {
                const linesToLoad = await this.orm.call(
                    "account.bank.statement.line",
                    "set_account_bank_statement_line",
                    [selectedLinesIds, suspenseLineIds, account[0]],
                    { context: { account_default_taxes: true } }
                );
                await this.bankReconciliation.reloadRecords(
                    this.env.model.root.records.filter((record) =>
                        linesToLoad.includes(record.resId)
                    )
                );
                this.bankReconciliation.reloadChatter();
            },
        });
    }

    /**
     * Sets the account receivable on the current reconcile line.
     */
    async setAccountReceivableOnReconcileLines() {
        // Send a notification for reconciled lines present in all the selected lines
        this.sendAlreadyReconciledNotification();
        const selectedLines = this.selectedUnreconciledStatementLines;
        if (!selectedLines.length) {
            return;
        }
        let linesToLoad = [];
        for (const selectedLine of selectedLines) {
            const lines = await this.orm.call(
                "account.bank.statement.line",
                "set_account_bank_statement_line",
                [
                    selectedLine.resId,
                    selectedLine.data.line_ids.records.at(-1).resId,
                    await this.accountReconcileLine(selectedLine, "asset_receivable"),
                ]
            );
            linesToLoad.push(lines);
        }
        linesToLoad = linesToLoad.flat();
        await this.bankReconciliation.reloadRecords(
            this.env.model.root.records.filter((record) => linesToLoad.includes(record.resId))
        );
        this.bankReconciliation.reloadChatter();
    }

    /**
     * Sets the account payable on the current reconcile line..
     */
    async setAccountPayableOnReconcileLines() {
        // Send a notification for reconciled lines present in all the selected lines
        this.sendAlreadyReconciledNotification();
        const selectedLines = this.selectedUnreconciledStatementLines;
        if (!selectedLines.length) {
            return;
        }
        let linesToLoad = [];
        for (const selectedLine of selectedLines) {
            const lines = await this.orm.call(
                "account.bank.statement.line",
                "set_account_bank_statement_line",
                [
                    selectedLine.resId,
                    selectedLine.data.line_ids.records.at(-1).resId,
                    await this.accountReconcileLine(selectedLine, "liability_payable"),
                ]
            );
            linesToLoad.push(lines);
        }
        linesToLoad = linesToLoad.flat();
        await this.bankReconciliation.reloadRecords(
            this.env.model.root.records.filter((record) => linesToLoad.includes(record.resId))
        );
        this.bankReconciliation.reloadChatter();
    }

    async validateBankLines() {
        // Send a notification for validated lines present in all the selected lines
        this.sendAlreadyValidatedNotification();
        const selectedLines = this.selectedUnvalidatedStatementLines;
        if (!selectedLines.length) {
            return;
        }
        let linesToLoad = [];
        for (const selectedLine of selectedLines) {
            const recoModelId = selectedLine.data.line_ids.records
                .filter((record) => record.data.reconcile_model_id)
                .map((record) => record.data.reconcile_model_id.id)?.[0];
            if (recoModelId) {
                await this.orm.call("account.reconcile.model", "trigger_reconciliation_model", [
                    recoModelId,
                    selectedLine.resId,
                ]);
                selectedLine.load();
                continue;
            }

            await this.bankReconciliation.computeReconcileLineCountPerPartnerId(selectedLines);
            const reconcileCount =
                this.bankReconciliation.reconcileCountPerPartnerId[
                    selectedLine.data.partner_id.id
                ] ?? null;

            if (!selectedLine.data.partner_id || reconcileCount !== null) {
                continue;
            }

            const lines = await this.orm.call(
                "account.bank.statement.line",
                "set_account_bank_statement_line",
                [
                    selectedLine.resId,
                    selectedLine.data.line_ids.records.at(-1).resId,
                    await this.accountReconcileLine(
                        selectedLine,
                        selectedLine.data.amount < 0 ? "liability_payable" : "asset_receivable"
                    ),
                ]
            );
            linesToLoad.push(lines);
        }
        linesToLoad = linesToLoad.flat();
        await this.bankReconciliation.reloadRecords(
            this.env.model.root.records.filter((record) => linesToLoad.includes(record.resId))
        );
        this.bankReconciliation.reloadChatter();
    }

    async accountReconcileLine(selectedLine, account_type = "liability_payable") {
        let accountId;
        const propertyAccountId =
            account_type == "liability_payable"
                ? selectedLine.data.partner_id?.property_account_payable_id?.id
                : selectedLine.data.partner_id?.property_account_receivable_id?.id;
        if (propertyAccountId) {
            accountId = propertyAccountId;
        } else {
            const account = await this.orm.webSearchRead(
                "account.account",
                [
                    ["company_ids", "=", selectedLine.data.company_id.id],
                    ["account_type", "=", account_type],
                ],
                { specification: {}, limit: 1 }
            );
            accountId = account.records[0].id;
        }
        return accountId;
    }

    async triggerReconciliationModel(reconciliationModelId) {
        // Send a notification for reconciled lines present in all the selected lines
        this.sendAlreadyReconciledNotification();
        const selectedLinesIds = this.selectedUnreconciledStatementLinesIds;
        if (!selectedLinesIds.length) {
            return;
        }

        await this.orm.call("account.reconcile.model", "trigger_reconciliation_model", [
            reconciliationModelId,
            selectedLinesIds,
        ]);
        await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
            this.env.model.root.records
        );
        await this.bankReconciliation.reloadRecords(this.selectedUnreconciledStatementLines);
        this.bankReconciliation.reloadChatter();
    }

    get buttonsToDisplay() {
        return this.selectedUnreconciledStatementLines.length
            ? [
                  ...(this.selectedUnvalidatedStatementLines.length
                      ? [
                            {
                                label: _t("Validate"),
                                action: this.validateBankLines.bind(this),
                                isLarge: true,
                                primary: true,
                            },
                        ]
                      : []),
                  {
                      label: _t("Set Partner"),
                      action: this.setPartnerOnReconcileLine.bind(this),
                      isLarge: true,
                  },
                  {
                      label: _t("Set Account"),
                      action: this.setAccountOnReconcileLine.bind(this),
                      isLarge: true,
                  },
              ]
            : [];
    }

    get selectedUnvalidatedStatementLines() {
        return this.selectedUnreconciledStatementLines.filter((line) => {
            const hasReconcileModel = line.data.line_ids?.records?.some(
                (record) => record.data.reconcile_model_id
            );

            const partnerId = line.data.partner_id?.id;
            const isReconcileCountNull =
                this.bankReconciliation.reconcileCountPerPartnerId[partnerId] == null;

            return hasReconcileModel || (isReconcileCountNull && partnerId);
        });
    }

    get selectedUnreconciledStatementLines() {
        return this.selectedStatementLines.filter((line) => !line.data.is_reconciled);
    }

    get selectedReconciledStatementLines() {
        return this.selectedStatementLines.filter((line) => line.data.is_reconciled);
    }

    get selectedUnreconciledStatementLinesIds() {
        return this.selectedUnreconciledStatementLines.map((line) => line.resId);
    }

    get selectedStatementLinesPartnerName() {
        return this.selectedStatementLines
            .filter((line) => !line.data.is_reconciled && line.data.partner_name)
            .map((line) => line.data.partner_name);
    }

    get selectedStatementLines() {
        return this.env.model.root.selection;
    }

    get reconcileModelsToDisplay() {
        if (this.selectedUnreconciledStatementLinesIds.length === 1) {
            return (
                this.bankReconciliation.reconcileModelPerStatementLineId[
                    this.selectedUnreconciledStatementLinesIds[0]
                ] ?? []
            );
        }

        const allReconcileModels = [];
        for (const statementLineId of this.selectedUnreconciledStatementLinesIds) {
            const reconcileModels =
                this.bankReconciliation.reconcileModelPerStatementLineId[statementLineId] ?? [];
            allReconcileModels.push(reconcileModels);
        }

        if (!allReconcileModels.length) {
            return [];
        }

        const intersection = allReconcileModels.pop();
        const remainingRecoModels = allReconcileModels.flat().map((recoModel) => recoModel.id);
        return intersection.filter((item) => remainingRecoModels.includes(item.id));
    }

    get extraButtonToDisplay() {
        const buttonsToDisplay = {};
        if (this.selectedUnreconciledStatementLines.length) {
            buttonsToDisplay.receivable = {
                label: _t("Receivable"),
                action: this.setAccountReceivableOnReconcileLines.bind(this),
            };
            buttonsToDisplay.payable = {
                label: _t("Payable"),
                action: this.setAccountPayableOnReconcileLines.bind(this),
            };
        }
        return Object.values(buttonsToDisplay);
    }
}
