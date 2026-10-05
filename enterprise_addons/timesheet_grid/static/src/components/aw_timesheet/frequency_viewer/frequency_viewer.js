import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, EventBus, onWillStart, useProps } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { ListRenderer } from "@web/views/list/list_renderer";
import { FrequencyViewerLocalConfig } from "./frequency_viewer_local_config";
import { useService } from "@web/core/utils/hooks";

export class FrequencyViewer extends Component {
    static template = "timesheet_grid.FrequencyViewer";
    static components = { ListRenderer };

    props = useProps(standardActionServiceProps);

    get fields() {
        return {
            row_title: { type: "char", name: "row_title", string: _t("Window") },
            project: { type: "char", name: "project", string: _t("Project") },
            task: { type: "char", name: "task", string: _t("Task") },
            count: { type: "integer", name: "count", string: _t("Freq") },
        };
    }

    get idToModel() {
        return {
            project_id: "project.project",
            task_id: "project.task",
        };
    }

    setup() {
        this.orm = useService("orm");
        this.localConfig = new FrequencyViewerLocalConfig();
        onWillStart(async () => {
            const scores = this.localConfig.scores;
            const ids = this.collectIds(scores);
            const names = await this.fetchNames(ids);
            const records = this.frequencyToRecords(scores, names);
            this.fakeList = this.makeFakeList(records);
            this.fakeArchInfo = this.makeFakeArchInfo();
        });
    }

    getRecordData(parsed, names) {
        return {
            project: names.project_id?.[parsed.project_id],
            task: names.task_id?.[parsed.task_id],
        };
    }

    collectIds(freq) {
        const ids = Object.fromEntries(Object.keys(this.idToModel).map((k) => [k, new Set()]));
        for (const combos of Object.values(freq)) {
            for (const jsonKey of Object.keys(combos)) {
                const parsed = JSON.parse(jsonKey);
                for (const field of Object.keys(ids)) {
                    if (parsed[field]) {
                        ids[field].add(parsed[field]);
                    }
                }
            }
        }
        return ids;
    }

    async fetchNames(ids) {
        const names = {};
        for (const [field, model] of Object.entries(this.idToModel)) {
            const idList = [...(ids[field] || [])];
            if (idList.length) {
                const results = await this.orm.read(model, idList, ["display_name"]);
                names[field] = Object.fromEntries(results.map((r) => [r.id, r.display_name]));
            } else {
                names[field] = {};
            }
        }
        return names;
    }

    frequencyToRecords(freq, names) {
        const records = [];
        let idx = 0;
        for (const [rowTitle, combos] of Object.entries(freq)) {
            for (const [jsonKey, count] of Object.entries(combos)) {
                const parsed = JSON.parse(jsonKey);
                records.push(
                    this.makeFakeRecord(idx++, {
                        row_title: rowTitle,
                        ...this.getRecordData(parsed, names),
                        count,
                    })
                );
            }
        }
        records.sort((a, b) => b.data.count - a.data.count);
        return records;
    }

    makeFakeRecord(id, data) {
        return {
            id,
            data,
            fields: this.fields,
            isFieldInvalid: () => false,
        };
    }

    makeFakeColumns() {
        return Object.entries(this.fields).map(([name, field]) => ({
            type: "field",
            name,
            id: name,
            label: field.string,
            hasLabel: true,
            attrs: {},
            options: {},
            field: {},
            fieldType: field.type,
        }));
    }

    makeFakeArchInfo() {
        return {
            columns: this.makeFakeColumns(),
            groupBy: { buttons: {} },
            controls: [],
            decorations: [],
        };
    }

    makeFakeList(records) {
        const fields = this.fields;
        const bus = new EventBus();
        return {
            records,
            model: { bus },
            selection: [],
            fields,
            activeFields: Object.fromEntries(Object.keys(fields).map((name) => [name, { name }])),
            fieldNames: Object.keys(fields),
            canResequence: () => false,
            orderBy: [],
            groupBy: [],
            toggleSelection: () => {},
            leaveEditMode: () => {},
            context: {},
        };
    }

    get listRendererProps() {
        return {
            list: this.fakeList,
            archInfo: this.fakeArchInfo,
            openRecord: () => {},
            readonly: true,
        };
    }
}

registry.category("actions").add("frequency_viewer", FrequencyViewer);
