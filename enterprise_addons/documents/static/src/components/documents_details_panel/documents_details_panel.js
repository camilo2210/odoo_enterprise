import { _t } from "@web/core/l10n/translation";
import { ModelSelector } from "@web/core/model_selector/model_selector";
import { user } from "@web/core/user";
import { memoize } from "@web/core/utils/functions";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { CharField } from "@web/views/fields/char/char_field";
import { Many2OneAvatarField } from "@web/views/fields/many2one_avatar/many2one_avatar_field";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

import { DocumentsDetailsMany2ManyTagsField } from "@documents/views/fields/documents_details_many2many_tags/documents_details_many2many_tags_field";
import { DocumentsDetailsMany2OneField } from "@documents/views/fields/documents_details_many2one/documents_details_many2one_field";
import { DocumentsTypeIcon } from "@documents/views/fields/documents_type_icon/documents_type_icon";

import { Component, computed, useProps, proxy, t, useEffect } from "@odoo/owl";

// Small hack, memoize uses the first argument as cache key, but we need the orm which will not be the same.
const getDetailsPanelResModels = memoize((_null, orm) =>
    orm.call("documents.document", "get_details_panel_res_models")
);

export class DocumentsDetailsPanel extends Component {
    static components = {
        CharField,
        DocumentsDetailsMany2ManyTagsField,
        DocumentsDetailsMany2OneField,
        DocumentsTypeIcon,
        Many2OneAvatarField,
        Many2OneField,
        ModelSelector,
    };
    props = useProps({
        record: t.object().optional(),
        nbViewItems: t.number().optional(),
    });
    static template = "documents.DocumentsDetailsPanel";

    setup() {
        this.action = useService("action");
        /** @type {import("@documents/core/document_service").DocumentService} */
        this.documentService = useService("document.document");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.record = computed(
            () => new Proxy(proxy(this.props.record), isDetailsPanelRecordHandler)
        );

        // Use a state for the model to not write on the record the model without record id
        this.state = proxy({
            resModel: this.props.record.data.res_model,
            resModelName: this.props.record.data.res_model_name || "",
            models: [],
        });
        getDetailsPanelResModels(null, this.orm).then((models) => (this.state.models = models));
        useEffect(() => {
            const data = this.props.record.data;
            this.state.resModel = data.res_model;
            this.state.resModelName = data.res_model_name || "";
        });
    }

    async openLinkedRecord() {
        const { res_model, res_id } = this.record().data || {};
        if (!res_id?.resId || !res_model) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_id: res_id.resId,
            res_model,
            views: [[false, "form"]],
            target: "current",
        });
    }

    get canChangeOwner() {
        return (
            !this.userPermissionViewOnly &&
            (this.documentService.userIsDocumentManager ||
                (!this.record().data?.owner_id && this.record().data?.user_can_move) ||
                this.record().data?.owner_id?.id === user.userId)
        );
    }

    get userPermissionViewOnly() {
        return (
            !!this.record().data?.lock_uid ||
            this.record().data?.user_permission !== "edit" ||
            Boolean(this.record().data?.is_protected)
        );
    }

    get fileSize() {
        if (this.record().data?.type !== "folder" || this.props.record.isContainer) {
            const nBytes = this.record().data.file_size || 0;
            if (nBytes) {
                return `${this.record().isContainer ? "~" : ""}${formatFloat(nBytes, {
                    humanReadable: true,
                })}B`;
            }
        }
        return "";
    }

    get rootFolderPlaceholder() {
        return {
            MY: _t("My Drive"),
            COMPANY: _t("Company"),
            SHARED: _t("Shared with me"),
        }[this.props.record.data?.user_folder_id];
    }

    get activeCompanies() {
        return user.activeCompanies.map((c) => c.id);
    }

    async onModelSelected(value) {
        const { technical: resModel, label: resModelName } = value;
        this.state.resModel = resModel;
        this.state.resModelName = resModelName || "";
        if (!resModel) {
            await this.props.record.update({ res_id: false, res_model: false }, { save: true });
            return;
        }
        this.notification.add(
            _t("Anyone with access to the linked record will be able to access the attachment."),
            {
                title: _t("Caution"),
                type: "warning",
            }
        );
        this.dialog.add(
            SelectCreateDialog,
            {
                title: _t("Select a Record To Link"),
                noCreate: true,
                multiSelect: false,
                resModel,
                onSelected: async (resIds) => {
                    if (resIds.length) {
                        await this.props.record.update(
                            { res_id: resIds[0], res_model: resModel },
                            { save: true }
                        );
                    }
                },
            },
            {
                onClose: () => {
                    if (!this.record().data.res_id) {
                        this.onRecordReset();
                    }
                },
            }
        );
    }

    async onRecordReset() {
        await this.onModelSelected({ technical: false, label: false });
    }
}

/**
 * Return isDetailsPanelRecord = true to prevent multi edit when editing a focused record from the
 * details panel but not from the list rows.
 * @type ProxyHandler
 */
const isDetailsPanelRecordHandler = {
    get(target, prop, receiver) {
        return prop === "isDetailsPanelRecord" || Reflect.get(...arguments);
    },
};
