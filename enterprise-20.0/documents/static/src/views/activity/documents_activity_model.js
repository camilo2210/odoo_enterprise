import { Domain } from "@web/core/domain";
import { DocumentsModelMixin } from "../documents_model_mixin";
import { DocumentsRecordMixin } from "../documents_record_mixin";
import { activityView } from "@mail/views/web/activity/activity_view";

const ActivityModel = activityView.Model;

export class DocumentsActivityModel extends DocumentsModelMixin(ActivityModel) {
    /**
     * Overridden to select documents of the selected folder.
     * @override
     */
    async load(params = {}) {
        return await super.load({
            ...params,
            domain: Domain.and([
                params.domain || [],
                this.env.searchModel._getCategoryDomain(),
            ]).toList(),
        });
    }
}

DocumentsActivityModel.Record = class DocumentsActivityRecord extends (
    DocumentsRecordMixin(ActivityModel.Record)
) {};
