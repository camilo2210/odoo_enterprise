import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { AttachDocumentWidget, attachDocumentWidget } from "@web/views/widgets/attach_document/attach_document";

export class PlanningSlotPhotosWidget extends AttachDocumentWidget {
    static template = "planning_field_service_worksheet.PlanningSlotPhotosWidget";

    get photoCount() {
        return this.props.record.data.photo_ids?.count;
    }

    get label() {
        let label = this.props.string;
        if (this.photoCount) {
            label = `${this.photoCount} ${label}`;
        }
        return label;
    }

    async onFileUploaded(files) {
        if (files.length) {
            this.notification.add(_t("Photos added"), { type: "success" });
            await this.props.record.load();
        }
    }
}

export const planningSlotPhotosWidget = {
    ...attachDocumentWidget,
    component: PlanningSlotPhotosWidget,
}

registry.category("view_widgets").add("planning_slot_photos_widget", planningSlotPhotosWidget);
