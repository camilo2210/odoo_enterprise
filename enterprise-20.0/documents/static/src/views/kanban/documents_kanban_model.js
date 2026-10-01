import { RelationalModel } from "@web/model/relational_model/relational_model";
import { DocumentsModelMixin } from "../documents_model_mixin";
import { DocumentsRecordMixin } from "../documents_record_mixin";

export class DocumentsKanbanModel extends DocumentsModelMixin(RelationalModel) {
    async _loadData(config) {
        const data = await super._loadData(config);
        await this._loadDocumentToRestore(config, data);
        return data;
    }
}

export class DocumentsKanbanRecord extends DocumentsRecordMixin(RelationalModel.Record) {
    async onReplaceDocument(ev) {
        if (!ev.target.files.length) {
            return;
        }
        await this.model.env.documentsView.bus.trigger("documents-upload-files", {
            files: ev.target.files,
            accessToken: this.data.access_token,
            context: {
                document_id: this.data.id,
            },
        });
        ev.target.value = "";
    }
}
DocumentsKanbanModel.Record = DocumentsKanbanRecord;
