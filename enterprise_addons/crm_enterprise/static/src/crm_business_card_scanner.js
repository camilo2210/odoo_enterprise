import { Component } from "@odoo/owl";

import { FileUploader } from "@web/views/fields/file_handler";
import { useService } from "@web/core/utils/hooks";
import { isMobileOS } from "@web/core/browser/feature_detection";


export class CrmBusinessCardScanner extends Component {
    static template = "crm_enterprise.CrmBusinessCardScanner";
    static components = {
        FileUploader,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.businessCardsAttachmentsIds = [];
        this.isMobileOS = isMobileOS();
    }

    async onFileUploaded(file) {
        const attachmentData = {
            name: file.name,
            type: 'binary',
            mimetype: file.type,
            raw: file.data,
        };
        this.env.services.ui.block();
        try {
            const [attachmentId] = await this.orm.create("ir.attachment", [attachmentData]);
            await this.orm.call(
                "ir.attachment",
                "generate_access_token",
                [attachmentId]
            );
            this.businessCardsAttachmentsIds.push(attachmentId);
        } finally {
            this.env.services.ui.unblock();
        }
    }

    async onUploadComplete() {
        this.env.services.ui.block();
        try {
            const context = {};
            const default_team_id = this.env.searchModel.context.default_team_id;
            if (default_team_id) {
                context.default_team_id = default_team_id;
            }
            const actionValues = await this.orm.call(
                "crm.lead",
                "action_ocr_business_cards",
                [[], this.businessCardsAttachmentsIds],
                { context },
            );
            if (actionValues) {
                this.action.doAction(actionValues);
            }
        } finally {
            this.businessCardsAttachmentsIds = [];
            this.env.services.ui.unblock();
        }
    }
}
