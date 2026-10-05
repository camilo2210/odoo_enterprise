import { describe, expect, test, beforeEach } from "@odoo/hoot";
import { Component, t, useProps, xml } from "@odoo/owl";
import { mountWithCleanup, contains, fields } from "@web/../tests/web_test_helpers";
import { defineSpreadsheetModels, Partner, Product } from "@spreadsheet/../tests/helpers/data";
import { SidepanelModelFieldSelector } from "@spreadsheet_edition/bundle/components/sidepanel_model_field_selector/sidepanel_model_field_selector";

describe.current.tags("desktop");
defineSpreadsheetModels();

async function mountSelector(canFollowComputedRelation) {
    class Wrapper extends Component {
        static template = xml`
            <SidepanelModelFieldSelector
                resModel="'partner'"
                readonly="false"
                canFollowComputedRelation="this.props.canFollowComputedRelation"
            />
        `;
        static components = { SidepanelModelFieldSelector };

        props = useProps({
            canFollowComputedRelation: t.boolean(),
        });
    }
    await mountWithCleanup(Wrapper, { props: { canFollowComputedRelation } });
    await contains(".add-dimension.o-button").click();
}

function getRelationSelector(field) {
    return `.o_model_field_selector_popover_item[data-name="${field}"] .o_model_field_selector_popover_item_relation`;
}

function getSelector(field) {
    return `.o_model_field_selector_popover_item[data-name="${field}"]`;
}

beforeEach(() => {
    Partner._fields.computed_product_id = fields.Many2one({
        string: "Product (non-stored)",
        relation: "product",
        store: false,
        searchable: true,
        groupable: true,
    });
});

describe("Non-stored fields can be followed", () => {
    Partner._fields.computed_product_id = fields.Many2one({
        string: "Product (non-stored)",
        relation: "product",
        store: false,
        searchable: true,
        groupable: true,
    });
    test("non-stored many2one has no follow-relation arrow without canFollowComputedRelation", async () => {
        await mountSelector(false);
        expect(getRelationSelector("product_id")).toHaveCount(1);
        expect(getRelationSelector("computed_product_id")).toHaveCount(0);
    });

    test("non-stored many2one has follow-relation arrow with canFollowComputedRelation=true", async () => {
        await mountSelector(true);
        expect(getRelationSelector("product_id")).toHaveCount(1);
        expect(getRelationSelector("computed_product_id")).toHaveCount(1);
    });
});

test("can select property fields", async () => {
    Product._records = [
        {
            id: 1,
            properties_definitions: [
                { name: "dbfc66e0afaa6a8d", type: "date", string: "prop 1" },
                { name: "f80b6fb58d0d4c72", type: "integer", string: "prop 2" },
            ],
        },
    ];
    Partner._records = [
        {
            product_id: 1,
            partner_properties: {
                dbfc66e0afaa6a8d: false,
                f80b6fb58d0d4c72: 0,
            },
        },
    ];

    await mountSelector(false);
    await contains(getRelationSelector("partner_properties")).click();
    expect(getSelector("dbfc66e0afaa6a8d")).toHaveCount(1);
    expect(getSelector("f80b6fb58d0d4c72")).toHaveCount(1);
});
