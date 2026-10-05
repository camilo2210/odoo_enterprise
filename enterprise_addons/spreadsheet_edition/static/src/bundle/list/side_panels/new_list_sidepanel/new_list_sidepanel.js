import { components } from "@odoo/o-spreadsheet";
import { Component, proxy, t, useProps } from "@odoo/owl";
import { ModelSelector } from "@web/core/model_selector/model_selector";
import { useService } from "@web/core/utils/hooks";
import { ListArchParser } from "@web/views/list/list_arch_parser";
import { parseXML } from "@web/core/utils/xml";
import { nbsp } from "@web/core/utils/strings";
import { waitForDataLoaded } from "@spreadsheet/helpers/model";
import { range } from "@web/core/utils/numbers";

const { Section } = components;

const rejectedFieldTypes = ["binary", "json"];
const RECORDS_TO_INSERT = 80;

export class NewListSidePanel extends Component {
    static template = "spreadsheet_edition.NewListSidePanel";
    static components = {
        Section,
        ModelSelector,
    };

    props = useProps({
        onCloseSidePanel: t.function(),
    });

    setup() {
        this.state = proxy({ model: undefined });
        this.viewService = useService("view");
        this.fieldService = useService("field");
    }

    get isSaveAllowed() {
        return this.state.model;
    }

    onModelSelected(model) {
        this.state.model = model;
    }

    async _getPropertyColumns(resModel, propertyField) {
        const { modelsInfo } = await this.fieldService.loadPath(resModel, `${propertyField}.*`);
        const { fieldDefs } = modelsInfo.at(-1);
        return Object.entries(fieldDefs).map(([name, field]) => ({
            name: `${propertyField}.${name}`,
            string: field.string,
        }));
    }

    async _getList() {
        const { fields, views } = await this.viewService.loadViews({
            resModel: this.state.model.technical,
            views: [[false, "list"]],
        });

        const archXmlDoc = parseXML(views.list.arch.replace(/&amp;nbsp;/g, nbsp));
        const archInfo = new ListArchParser().parse(
            archXmlDoc,
            { [this.state.model.technical]: { fields } },
            this.state.model.technical
        );

        const columns = [];
        for (const column of archInfo.columns) {
            if (
                rejectedFieldTypes.includes(column.fieldType) ||
                column.optional === "hide" ||
                column.column_invisible ||
                column.type !== "field"
            ) {
                continue;
            }
            if (column.fieldType === "properties") {
                columns.push(
                    ...(await this._getPropertyColumns(this.state.model.technical, column.name))
                );
            } else {
                columns.push({ name: column.name, string: column.string });
            }
        }

        if (columns.length === 0) {
            columns.push({ name: "id", string: "ID" });
        }

        return {
            model: this.state.model.technical,
            name: this.state.model.label,
            columns: columns,
            domain: [],
            context: {},
            orderBy: [],
        };
    }

    async save() {
        const listId = this.env.model.getters.getNextListId();
        const definition = await this._getList();

        const result = this.env.model.dispatch("INSERT_NEW_ODOO_LIST", {
            listId,
            name: definition.name,
            linesNumber: RECORDS_TO_INSERT,
            definition,
            insertInNewSheet: true,
            mode: "dynamic",
        });
        if (!result.isSuccessful) {
            throw new Error(`Couldn't insert list in spreadsheet. Reasons : ${result.reasons}`);
        }
        await waitForDataLoaded(this.env.model);
        const sheetId = this.env.model.getters.getActiveSheetId();
        const cols = range(0, definition.columns.length);
        this.env.model.dispatch("AUTORESIZE_COLUMNS", { sheetId, cols });

        const rows = range(0, RECORDS_TO_INSERT + 1);
        this.env.model.dispatch("AUTORESIZE_ROWS", { sheetId, rows });

        this.env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    }
}
