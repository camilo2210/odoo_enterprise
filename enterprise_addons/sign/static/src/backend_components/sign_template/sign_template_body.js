import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { SignTemplateIframe } from "./sign_template_iframe";
import {
    Component,
    onMounted,
    onPatched,
    onWillUnmount,
    onWillStart,
    proxy,
    signal,
    t,
    useListener,
    useProps,
} from "@odoo/owl";
import { buildPDFViewerURL, injectPDFCustomStyles } from "@sign/components/sign_request/utils";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { hidePDFJSButtons } from "@web/core/utils/pdfjs";
import { SignSaveTemplateDialog } from "./sign_save_template_dialog";
import { user } from "@web/core/user";

export class SignTemplateBody extends Component {
    static template = "sign.SignTemplateBody";
    static components = {
        SignSaveTemplateDialog,
    };

    props = useProps({
        signItemTypes: t.array(),
        fetchSignItemTypes: t.function().optional(),
        signItems: t.array().optional(),
        radioSets: t.object().optional(),
        hasSignRequests: t.boolean(),
        signItemOptions: t.array(),
        attachmentLocation: t.string(),
        signTemplate: t.object(),
        goBackToKanban: t.function(),
        onTemplateSaveClick: t.function(),
        manageTemplateAccess: t.boolean(),
        resModel: t.string(),
        signStatus: t.object(),
        iframe: t.object().optional(),
        setIframe: t.function(),
        documentId: t.number(),
        updateSignItemsCountCallback: t.function(),
    });

    PDFIframeRef = signal.ref();

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.popover = useService("popover");
        this.dialog = useService("dialog");
        this.PDFViewerURL = buildPDFViewerURL(this.props.attachmentLocation);
        this.state = proxy({
            documentUsedTimesCounter: 0,
        });
        onMounted(() => {
            const el = this.PDFIframeRef();
            if (el) {
                hidePDFJSButtons(el, {
                    hideDownload: true,
                    hidePrint: true,
                    hidePresentation: true,
                    hideRotation: true,
                });
            }
            this.waitForPDF();
        });
        onPatched(() => {
            this.waitForPDF();
        });

        useListener(document, "visibilitychange", () => {
            if (document.visibilityState === "hidden") {
                this.props.signStatus.save();
            }
        });

        onWillUnmount(() => {
            const iframeDoc = this.PDFIframeRef()?.contentDocument;
            if (iframeDoc && this._onIframeClick) {
                iframeDoc.removeEventListener("click", this._onIframeClick);
            }
            if (this.props.iframe) {
                this.props.iframe.unmount();
                this.props.setIframe(null);
            }
        });

        onWillStart(async () => {
            if (!this.props.signTemplate.active) {
                /* When uploading a PDF for signing, we check how many times a PDF with that
                name was used and if it is bigger than two, then suggest the user saving it
                as template with in a notification with a button. */
                const documentUsedTimes = await this.orm.searchCount("sign.request", [
                    ["reference", "ilike", this.props.signTemplate.display_name],
                ]);
                this.state.documentUsedTimesCounter = documentUsedTimes;
            }

            return await Promise.all([this.fetchRadioSets(), this.fetchSignItemData()]);
        });
    }

    async fetchRadioSets() {
        this.radioSets = await this.orm.call("sign.document", "get_radio_sets_dict", [
            this.props.documentId,
        ]);
    }

    async fetchSignItemData() {
        this.signItems = await this.orm.call(
            "sign.item",
            "search_read",
            [[["document_id", "=", this.props.documentId]]],
            { context: user.context }
        );

        this.signItems.forEach((item) => {
            item.type_id = item.type_id[0];
            item.radio_set_id = item?.radio_set_id[0] || undefined;
            item.roleName = item.responsible_id[1];
            item.document_id = item.document_id[0];
        });
    }

    // Dropdowns rely on document clicks; iframe clicks don't propagate, so close all dropdowns manually
    attachDropdownCloseOnIframeClick(iframeDoc) {
        if (!iframeDoc) {
            return;
        }
        if (this._onIframeClick) {
            iframeDoc.removeEventListener("click", this._onIframeClick);
        }
        this._onIframeClick = () => {
            document.querySelectorAll(".o-dropdown--menu").forEach((menu) => menu.remove());
        };
        iframeDoc.addEventListener("click", this._onIframeClick);
    }

    waitForPDF() {
        this.PDFIframeRef().onload = () => {
            injectPDFCustomStyles(this.PDFIframeRef().contentDocument);
            this.attachDropdownCloseOnIframeClick(this.PDFIframeRef().contentDocument);
            setTimeout(() => this.doPDFPostLoad(), 1);
        };
    }

    doPDFPostLoad() {
        this.preventDroppingImagesOnViewerContainer();
        const iframe = new SignTemplateIframe(
            this.PDFIframeRef().contentDocument,
            this.env,
            {
                orm: this.orm,
                popover: this.popover,
                dialog: this.dialog,
                notification: this.notification,
            },
            {
                signItemTypes: this.props.signItemTypes,
                signItems: this.signItems,
                hasSignRequests: this.props.hasSignRequests,
                signItemOptions: this.props.signItemOptions,
                radioSets: this.radioSets,
                saveTemplate: () => this.saveTemplate(),
                getRadioSetInfo: (id) => this.getRadioSetInfo(id),
                signStatus: this.props.signStatus,
                setTemplateChangedState: (state) =>
                    (this.props.signStatus.isTemplateChanged = state),
                documentId: this.props.documentId,
                updateSignItemsCountCallback: this.props.updateSignItemsCountCallback,
            }
        );
        this.props.setIframe(iframe);
    }

    /**
     * Prevents opening files in the pdf js viewer when dropping files/images to the viewerContainer
     * Ref: https://stackoverflow.com/a/68939139
     */
    preventDroppingImagesOnViewerContainer() {
        const viewerContainer =
            this.PDFIframeRef().contentDocument.querySelector("#viewerContainer");
        viewerContainer.addEventListener(
            "drop",
            (e) => {
                if (e.dataTransfer.files && e.dataTransfer.files.length) {
                    e.stopImmediatePropagation();
                    e.stopPropagation();
                }
            },
            true
        );
    }

    async saveTemplate(newTemplateName) {
        const [updatedSignItems, Id2UpdatedItem] = this.prepareTemplateData();
        const newId2ItemIdMap = await this.orm.call("sign.template", "update_from_pdfviewer", [
            this.props.signTemplate.id,
            updatedSignItems,
            this.props.iframe?.deletedSignItemIds,
            newTemplateName || "",
        ]);

        if (!newId2ItemIdMap) {
            // updatedSignItems returns {} if there are no changes to be saved.
            // In this case, we don't need to show the dialog.
            if (updatedSignItems && Object.keys(updatedSignItems).length > 0) {
                this.showBlockedTemplateDialog();
            }
            return false;
        }

        for (const [newId, itemId] of Object.entries(newId2ItemIdMap)) {
            Id2UpdatedItem[newId].id = itemId;
        }
        return Id2UpdatedItem;
    }

    async getRadioSetInfo(sign_item_ids) {
        const info = await this.orm.call("sign.template", "get_radio_set_info_by_item_id", [
            this.props.signTemplate.id,
            sign_item_ids,
        ]);
        return info;
    }

    prepareTemplateData() {
        const updatedSignItems = {};
        const Id2UpdatedItem = {};
        const items = this.props.iframe?.signItems ?? {};
        for (const page in items) {
            for (const id in items[page]) {
                const signItem = items[page][id].data;
                if (signItem.updated) {
                    Id2UpdatedItem[id] = signItem;
                    const responsible = signItem.responsible;
                    updatedSignItems[id] = {
                        type_id: signItem.type_id,
                        required: signItem.required,
                        constant: signItem.constant,
                        name: signItem.placeholder || signItem.name,
                        alignment: signItem.alignment,
                        option_ids: signItem.option_ids,
                        responsible_id: responsible,
                        page: page,
                        posX: signItem.posX,
                        posY: signItem.posY,
                        width: signItem.width,
                        height: signItem.height,
                        radio_set_id: signItem.radio_set_id,
                        document_id: signItem.document_id,
                    };

                    if (id < 0) {
                        updatedSignItems[id]["transaction_id"] = id;
                    }
                }
            }
        }
        return [updatedSignItems, Id2UpdatedItem];
    }

    showBlockedTemplateDialog() {
        this.dialog.add(AlertDialog, {
            confirm: () => {
                this.props.goBackToKanban();
            },
            body: _t("Somebody is already filling a document which uses this template"),
        });
    }
}
