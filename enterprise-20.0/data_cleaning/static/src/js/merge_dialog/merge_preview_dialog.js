import { Component, onWillStart, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MergeDetailsDialog extends Component {
    static template = "data_cleaning.MergeDetailsDialog";
    static components = { Dialog };

    props = useProps({
        groupId: t.number(),
        recordId: t.number(),
        close: t.function(),
    });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.previewData = null;

        onWillStart(async () => {
            const data = await this.orm.call(
                "data_merge.group",
                "get_merge_preview",
                [[this.props.groupId], this.props.recordId]
            );
            this.previewData = Object.keys(data).length ? data : null;
        });
    }

    get totalFieldsDeleted() {
        return this.previewData?.master_exclusive?.length || null;
    }

    get totalSourceRecords() {
        const relations = this.previewData?.merged_relations;
        if (!relations?.length) return null;
        return relations.reduce((sum, rel) => sum + rel.source_count, 0);
    }

    get matchRatio() {
        const mapping = this.previewData?.deduplication_rule_mapping;
        if (!mapping) return null;
        const fields = Object.values(mapping);
        return { matching: fields.filter((f) => f.is_match).length, total: fields.length };
    }

    /**
    * Open related records linked to master or source.
    * @param {Object} rel - Relation data from `merged_relations` returned by `_get_relation_preview`
    * @param {number} id - Master or source record ID used for filtering
    */
    openRecords(rel, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: rel.model_label,
            res_model: rel.model,
            views: [[false, "list"]],
            domain: [[rel.field_name, "=", id]],
            target: "current",
        });
    }

}

registry.category("actions").add("data_merge_details_dialog", (env, action) => {
    const dialog = useService("dialog");

    const { group_id: groupId, record_id: recordId } = action.params || {};
    if (!groupId || !recordId) return;

    dialog.add(MergeDetailsDialog, { groupId, recordId });
});
