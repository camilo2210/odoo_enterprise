import { DataCleaningCommonListController } from "@data_recycle/views/data_cleaning_common_list";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched } from "@odoo/owl";
import { ListRenderer } from '@web/views/list/list_renderer';
import { listView } from '@web/views/list/list_view';
import {
    provideViewButtonHandler,
    useViewButtonHandler,
} from "@web/views/view_button/view_button_hook";
import { DataMergeGroupConfigMenu } from "./data_merge_group_config_menu";

export class DataMergeListModel extends listView.Model {}
export class DataMergeListRecord extends DataMergeListModel.Record {
    /**
    * @override
    */
    async _save() {
        await super._save(...arguments);
        await this.model.load();
        this.model.notify();
    }
}
DataMergeListModel.Record = DataMergeListRecord;

export class DataMergeListController extends DataCleaningCommonListController {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.actionService = useService("action");
        this.notificationService = useService("notification");
        const onClickViewButton = useViewButtonHandler();

        const refreshButtonsVisibility = () => {
            const selectedRecords = this.model.root.selection;

            // Check the active state of selected records
            const allInactive = selectedRecords.every(r => r.data.is_discarded === true);
            const allActive = selectedRecords.every(r => r.data.is_discarded === false);

            // Helper function to toggle the 'd-none' class
            const toggleBtnVisibility = (selector, shouldShow) => {
                const btn = document.querySelector(selector);
                if (btn) btn.classList.toggle('d-none', !shouldShow);
            };

            toggleBtnVisibility('button[name="action_validate_merge"]', allActive);
            toggleBtnVisibility('button[name="action_discard_selected_records"]', allActive);
            toggleBtnVisibility('button[name="action_undiscard_selected_records"]', allInactive);
        };
        onMounted(refreshButtonsVisibility);
        onPatched(refreshButtonsVisibility);

        provideViewButtonHandler((params) => {
            const paramsName = params.clickParams.name;
            const ResParams = params.getResParams();
            const groupId = ResParams.resId;
            const groupRecords = this.getGroupRecords(groupId);
            const recordIds = this.getRecordIDS(groupRecords);
            const action = (paramsName === 'merge_records' ? 'merge_records' : 'discard_records');

            if (paramsName === 'action_validate_merge') {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Merge Records"),
                    body: _t("Are you sure you want to merge these records in their respective groups? Like cream swirling into coffee, once done there is no way back."),
                    confirmLabel: _t("Merge all"),
                    confirm: async () => {
                        try {
                            await onClickViewButton(params);
                            this.showMergeNotification();
                            await this.model.load();
                        } catch (error) {
                            console.warn("Merge operation failed or timed out:", error);
                            this.notificationService.add(
                                _t("The connection timed out. Please try merging fewer records at once."),
                                { type: "warning", sticky: true }
                            );
                        }

                    },
                    cancel: () => {},
                });
            } else if (paramsName === 'merge_records') {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Merge Records"),
                    body: _t("Are you sure you want to merge these records? Like cream swirling into coffee, once done there is no way back."),
                    confirmLabel: _t("Merge"),
                    confirm: async () => {
                        await this.doActionMergeDiscard(paramsName, groupId, recordIds);
                    },
                    cancel: () => {},
                });
            } else if (paramsName === 'discard_records') {
                this.doActionMergeDiscard(action, groupId, recordIds);
            } else {
                onClickViewButton(params);
            }
        });
    }

    /**
     * Get the list of selected records for the specified group
     * @returns list of record IDs
     * @param {int} groupId
     */
    getGroupRecords(groupId) {
        let records = this.model.root.selection;
        if (!this.model.root.selection.length) {
            records = this.model.root.records;
        }
        return records.filter(record => record.data.group_id.id === groupId);
    }

    /**
     * Get the original record IDs
     * @param {int[]} records
     */
    getRecordIDS(records) {
        return records.map(record => parseInt(record.resId));
    }

    /**
     * Call the specified action
     * @param {string} action Action to perform (merge/discard)
     * @param {int} groupId ID of the data_merge.group
     * @param {int[]} recordIds Selected records to merge/discard
     */
    async _callAction(action, groupId, recordIds) {
        return this.orm.call('data_merge.group', action, [groupId, recordIds]);
    }

    async doActionMergeDiscard(action, groupId, recordIds) {
        let res = await this._callAction(action, groupId, recordIds)
        if (res && 'type' in res && res.type.startsWith('ir.actions')) {
            if(!('views' in res)) {
                res = Object.assign(res, {views: [[false, 'form']]});
            }
            this.actionService.doAction(res)
        } else if (res && res.back_to_model) {
            window.history.back();
        } else {
            if (action === 'merge_records') {
                const records_merged = res && 'records_merged' in res ? res.records_merged : false;
                this.showMergeNotification(records_merged);
            }
            await this.model.load();
        }
    }

    /**
     * Show a notification with the number of records merged
     * @param {int} records_merged
     */
    showMergeNotification(recordsMerged) {
        let message;
        if (recordsMerged) {
            message = _t("%s records have been merged", recordsMerged);
        } else {
            message = _t("The selected records have been merged");
        }
        this.notificationService.add(message, {});
    }
};

/**
 * Customize GroupConfigMenu for Data Merge.
 * Highlights the master record row when hovering the "Merge" button
 */
export class DataMergeListRenderer extends ListRenderer {
    static groupRowTemplate = "DataMergeListRenderer.GroupRow"

    static components = {
        ...ListRenderer.components,
        GroupConfigMenu: DataMergeGroupConfigMenu,
    };
    setup() {
        super.setup();
        this.highlightedRow = null;
    }

    /**
     * When hovering on the merge button inside a group row:
     * Find the master record of the group
     * Highlight its corresponding row in the list
     */
    onGroupRowMouseEnter(ev, group) {
        const btn = ev.target.closest("button");
        if (!btn || btn.name !== "merge_records") {
            return;
        }
        const master = group.list.records.find(r => r.data.is_master);
        if (!master) return
        const row = this.tableRef().querySelector(
            `tr.o_data_row[data-id="${master.id}"]`
        );
        row?.classList.add("table-active");
        this.highlightedRow = row
    }

    // Remove highlight when mouse leaves the merge button
    onGroupRowMouseLeave() {
        if (this.highlightedRow) {
            this.highlightedRow.classList.remove("table-active");
            this.highlightedRow = null;
        }
    }
}

registry.category('views').add('data_merge_list', {
    ...listView,
    Controller: DataMergeListController,
    Renderer: DataMergeListRenderer,
    Model: DataMergeListModel,
});
