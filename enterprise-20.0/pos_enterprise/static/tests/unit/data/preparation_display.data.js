import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models, MockServer } from "@web/../tests/web_test_helpers";

export class PosPrepDisplay extends models.ServerModel {
    _name = "pos.prep.display";

    _load_pos_data_fields() {
        return ["id", "category_ids", "write_date"];
    }

    _load_preparation_data_models() {
        return [
            "res.company",
            "res.currency",
            "pos.config",
            "pos.category",
            "pos.prep.order",
            "pos.order",
            "pos.prep.line",
            "pos.prep.stage",
            "product.product",
            "pos.preset",
            "product.attribute",
            "product.template.attribute.value",
            "resource.calendar.attendance",
            "product.attribute.custom.value",
            "pos.session",
            "pos.order.line",
            "pos.printer",
            "pos.prep.display",
            "ir.ui.view",
            "decimal.precision",
        ];
    }

    getModelsToLoad() {
        return this._load_preparation_data_models();
    }

    getModelFieldsToLoad(model) {
        return model._load_pos_preparation_data_fields
            ? model._load_pos_preparation_data_fields()
            : model._load_pos_data_fields();
    }

    getModelDependencies(model) {
        return [];
    }

    _load_data_relations(model, fields) {
        const response = {};
        const serverModel = MockServer.env[model];
        const posFields = this.getModelFieldsToLoad(serverModel);
        const allFields = serverModel.fields_get();
        const base = posFields.length ? posFields : Object.keys(allFields);

        if (!base.includes("id")) {
            base.push("id");
        }

        if (!base.includes("write_date")) {
            base.push("write_date");
        }

        for (const fieldName of base) {
            const field = allFields[fieldName];

            if (!field) {
                console.debug(`Field ${fieldName} not found in model ${model}`);
                continue;
            }

            response[fieldName] = {
                name: fieldName,
                model: model,
                compute: Boolean(field.compute),
                related: Boolean(field.related),
                type: field.type,
                relation: field.relation,
                inverse_name: field.inverse_fname_by_model_name?.[field.relation] || false,
            };
        }

        return response;
    }

    load_preparation_data() {
        const modelToLoad = this.getModelsToLoad();
        const response = modelToLoad.reduce((acc, modelName) => {
            acc[modelName] = {};
            return acc;
        }, {});

        for (const modelName of modelToLoad) {
            const model = MockServer.env[modelName];
            response[modelName].dependencies = this.getModelDependencies(model);
            response[modelName].fields = this.getModelFieldsToLoad(model);
            response[modelName].relations = this._load_data_relations(
                modelName,
                response[modelName].fields
            );
            const records = model.search_read(
                [],
                response[modelName].fields,
                false,
                false,
                false,
                false
            );
            for (const record of records) {
                if (!record.write_date) {
                    record.write_date = "2025-01-01 10:00:00";
                }
            }
            response[modelName].records = records;
        }
        return response;
    }

    pos_has_valid_product() {
        return true;
    }

    get_preparation_display_orders() {
        return {
            "pos.prep.order": [],
            "pos.prep.line": [],
            "pos.order": [],
            "product.product": [],
            "product.template.attribute.value": [],
            "product.attribute": [],
            "product.attribute.custom.value": [],
            "pos.order.line": [],
        };
    }

    _records = [
        {
            id: 1,
            category_ids: [1],
            write_date: "2025-07-22 15:19:30",
        },
    ];
}

patch(hootPosModels, [...hootPosModels, PosPrepDisplay]);
