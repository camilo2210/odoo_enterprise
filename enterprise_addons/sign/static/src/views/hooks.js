import { signal, useListener, useProps } from "@odoo/owl";
import { TemplateAlertDialog } from "@sign/backend_components/template_alert_dialog/template_alert_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { useEnv } from "@web/owl2/utils";

/**
 * @param {{ ignoreBusSubscription?: boolean }} [options]
 */
export function useSignViewButtons(options) {
    /**
     * Handles the template file upload logic.
     *
     * @param {(Event & { currentTarget: HTMLInputElement }) | CustomEvent<Iterable<File>>} ev
     * @param {string} [resModel]
     */
    async function onFileInputChange(ev, resModel = props.resModel) {
        const rawFiles = ev?.type === "change" ? ev.currentTarget.files : ev.detail.files;
        const referenceDoc =
            lastRequestExtraContext?.default_reference_doc ||
            env.searchModel?.globalContext?.default_reference_doc;
        if (!rawFiles?.length) {
            return;
        }
        const files = Array.from(rawFiles);
        if (files.filter((file) => file.type !== "application/pdf").length) {
            dialog.add(TemplateAlertDialog, {
                title: _t("File Error"),
                body: _t("Only PDF files are allowed."),
            });
            return;
        }
        if (props.signTemplateId) {
            await uploadFiles(files, resModel, referenceDoc);
            return props.updateDocuments?.();
        }
        const { id: template_id, name: template_name } = await uploadFiles(
            files,
            resModel,
            referenceDoc
        );
        return action.doAction({
            type: "ir.actions.client",
            tag: "sign.Template",
            name: template_name,
            params: {
                sign_edit_call: lastRequestContext,
                id: template_id,
                sign_directly_without_mail: false,
                resModel,
            },
            context: {
                default_reference_doc: referenceDoc,
                default_activity_id: env.searchModel?.globalContext?.default_activity_id,
                ...lastRequestExtraContext,
            },
        });
    }

    /**
     * Initiates the file upload process by opening a file input dialog
     * and configuring the 'save as template' button based on the provided model
     * and other properties.
     *
     * @param {string} context
     * @param {any} [extraContext]
     */
    function requestFile(context, extraContext = {}) {
        lastRequestContext = context;
        lastRequestExtraContext = extraContext;
        uploadFileInputRef().click();
    }

    /**
     * @param {File[]} files
     * @param {string} resModel
     * @param {any} referenceDoc
     */
    async function uploadFiles(files, resModel, referenceDoc) {
        // Templates created from the sign.template view are automatically active.
        // Templates created from other views are not automatically active and must be saved manually.
        const active = resModel === "sign.template" && !referenceDoc;
        const filesList = await Promise.all(
            files.map(async (file) => ({
                name: file.name,
                raw: (await getDataURLFromFile(file)).split(",")[1],
            }))
        );
        const context = user.context;
        if (referenceDoc) {
            const [modelName] = referenceDoc.split(",");
            context["default_model_name"] = modelName;
        }
        if (props.signTemplateId) {
            return orm.call(
                "sign.template",
                "update_from_attachment_data",
                [props.signTemplateId],
                { attachment_data_list: filesList, context: context }
            );
        } else {
            const isOneTimeRequest = !active;
            return orm.call(
                "sign.template",
                "create_from_attachment_data",
                [filesList, active, isOneTimeRequest],
                { context: context }
            );
        }
    }

    const props = useProps();
    const env = useEnv();
    const action = useService("action");
    const dialog = useService("dialog");
    const orm = useService("orm");
    const uploadFileInputRef = signal.ref(HTMLInputElement);
    let lastRequestContext;
    let lastRequestExtraContext;

    useListener(uploadFileInputRef, "change", onFileInputChange);

    if (!options?.ignoreBusSubscription) {
        useListener(env.bus, "change_file_input", async (ev) => {
            uploadFileInputRef().files = ev.detail.files;
            await onFileInputChange(ev, ev.detail.resModel);
        });
    }

    return {
        uploadFileInputRef,
        requestFile,
    };
}
