import { ORM } from "@web/core/orm_plugin";
import { user } from "@web/core/user";

import { Plugin, signal, types as t, useConfig, usePlugin } from "@odoo/owl";

export class AiAgentSourceFolderTreePlugin extends Plugin {
    orm = usePlugin(ORM);
    record = useConfig("record", t.record());
    list = useConfig("list", t.object());
    unfoldedIds = signal.Set(new Set(), { type: t.number() });
    records = signal.Array([]);
    canManageSources = signal(false);

    setup() {
        user.hasGroup("base.group_system").then((hasGroup) => this.canManageSources.set(hasGroup));
    }

    get rootRecords() {
        return this.records().filter((record) => !record.data.parent_id);
    }

    get childrenByParentId() {
        const records = this.records();
        if (this._childrenByParentId?.records !== records) {
            const byParentId = new Map();
            for (const record of records) {
                const parentId = record.data.parent_id && record.data.parent_id[0];
                if (parentId) {
                    if (!byParentId.has(parentId)) {
                        byParentId.set(parentId, []);
                    }
                    byParentId.get(parentId).push(record);
                }
            }
            this._childrenByParentId = { records, byParentId };
        }
        return this._childrenByParentId.byParentId;
    }

    childrenOf(parentResId) {
        return this.childrenByParentId.get(parentResId) || [];
    }

    async loadTree() {
        const rows = await this.orm.call("ai.agent.source", "get_agent_sources_tree", [
            this.record.resId,
            Object.keys(this.list.activeFields),
            [...this.unfoldedIds()],
        ]);
        this.records.set(rows.map((data) => ({ id: data.id, resId: data.id, data })));
    }

    async toggleFolder(record) {
        if (this.unfoldedIds().has(record.resId)) {
            this.unfoldedIds().delete(record.resId);
            return;
        }
        this.unfoldedIds().add(record.resId);
        if (!this.childrenOf(record.resId).length) {
            await this.loadTree();
        }
    }

    async reloadAll() {
        // Only the sources tree needs refreshing here: no field on the agent
        // record itself depends on source state, so reloading the parent
        // record would be wasted work. Saving first only guards against
        // clobbering an in-progress edit to another field (e.g. name).
        if (await this.record.isDirty()) {
            await this.record.save({ reload: false });
        }
        await this.loadTree();
    }

    patchRecord(resId, data) {
        this.records.set(
            this.records().map((record) =>
                record.resId === resId ? { ...record, data: { ...record.data, ...data } } : record
            )
        );
    }

    removeRecord(resId) {
        this.records.set(this.records().filter((record) => record.resId !== resId));
    }
}
