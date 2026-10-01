import { DocumentsControllerMixin } from "@documents/views/documents_controller_mixin";
import { DocumentsSelectionBox } from "@documents/views/selection_box/documents_selection_box";
import { ActivityController } from "@mail/views/web/activity/activity_controller";
import { _t } from "@web/core/l10n/translation";
import { omit } from "@web/core/utils/objects";
import { ActionMenus, STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

export class DocumentsActivityController extends DocumentsControllerMixin(ActivityController) {
    static template = "documents.DocumentsActivityController";
    static components = {
        ...ActivityController.components,
        ActionMenus,
        SelectionBox: DocumentsSelectionBox,
    };

    get rendererProps() {
        return Object.assign(super.rendererProps, {
            previewStore: this.previewStore(),
        });
    }

    get modelParams() {
        const modelParams = super.modelParams;
        modelParams.multiEdit = false;
        const state = {
            ...(this.props.state?.modelState || {}),
            // Reset selection because not supporting multi-selection and not displaying all records
            sharedSelection: [],
        };
        return {
            ...modelParams,
            state,
        };
    }

    /**
     * Select record for inspector.
     *
     * @override
     */
    async openRecord(record) {
        for (const record of this.model.root.selection) {
            record.selected = false;
        }
        record.selected = true;
        this.documentService.focusRecord(record);
        this.model.notify();
    }

    /**
     * @returns {Boolean} whether the record can be previewed in the attachment viewer.
     */
    isRecordPreviewable(record) {
        return (
            super.isRecordPreviewable(record) &&
            this.model.activityData.activity_res_ids.includes(record.resId)
        );
    }

    /**
     * @override
     * @param {number} [templateID]
     * @param {number} [activityTypeID]
     */
    sendMailTemplate(templateID, activityTypeID) {
        super.sendMailTemplate(templateID, activityTypeID);
        this.env.services.notification.add(_t("Reminder emails have been sent."), {
            type: "success",
        });
    }

    /**
     * See actionMenuProps
     */
    get actionMenuItems() {
        const { actionMenus } = this.props.info;
        const staticActionItems = Object.entries(this.getStaticActionMenuItems())
            .filter(([__, item]) => item.isAvailable === undefined || item.isAvailable())
            .sort(([k1, item1], [__, item2]) => (item1.sequence || 0) - (item2.sequence || 0))
            .map(([key, item]) =>
                Object.assign(
                    { key, groupNumber: STATIC_ACTIONS_GROUP_NUMBER },
                    omit(item, "isAvailable")
                )
            );

        return {
            action: staticActionItems.concat(actionMenus?.action || []),
            print: actionMenus?.print,
        };
    }

    /**
     * Similarly to kanban and list controller, we define this getter to provide the ActionMenus props for the selected
     * documents. To keep thing similar, we define the actionMenuItems getter as well which is used by this getter.
     * Those getters are not present in the base implementation because in other apps, we can't select records in the
     * activity view to apply an action on them (when clicking on a record, it opens the form view usually).
     */
    get actionMenuProps() {
        return {
            getActiveIds: () => this.model.root.selection.map((r) => r.resId),
            context: this.model.root.context,
            domain: this.props.domain,
            items: this.actionMenuItems,
            isDomainSelected: this.model.root.isDomainSelected,
            resModel: this.model.root.resModel,
            onActionExecuted: ({ noReload } = {}) => {
                if (!noReload) {
                    return this.model.load();
                }
            },
        };
    }
}
