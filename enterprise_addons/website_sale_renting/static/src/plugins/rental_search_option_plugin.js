import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { BuilderAction } from "@html_builder/core/builder_action";

export class RentalSearchOptionPlugin extends Plugin {
    static id = "rentalSearchOption";

    resources = {
        so_content_addition_selectors: [".s_rental_search"],
        builder_actions: {
            SetRentalSearchTimingAction,
            SetRentalSearchProductAttributeAction,
        },
        // TODO: this ressource is needed to avoid some unwanted spacing due to
        // a <br> tag being added by the html_editor. We should remove the div
        // .product_attribute_search_rental_name and make an upgrade: it's only
        // used to keep track of an ID. This should be kept somewhere else and
        // should not use an empty div.
        is_valid_for_base_container_predicates: (node) => {
            if (
                node.nodeType === Node.ELEMENT_NODE &&
                node.classList.contains("product_attribute_search_rental_name")
            ) {
                    return false;
            }
        },
    };
}

export class SetRentalSearchTimingAction extends BuilderAction {
    static id = "setRentalSearchTiming";
    isApplied({ editingElement, params: { mainParam: timing } }) {
        if (!editingElement.dataset.timing) {
            editingElement.dataset.timing = "days";
        }
        return editingElement.dataset.timing === timing;
    }
    apply({ editingElement, params: { mainParam: timing } }) {
        editingElement.dataset.timing = timing;
        editingElement.querySelector(".o_website_sale_daterange_picker").dataset.rentalDurationUnit = timing;
    }
}

export class SetRentalSearchProductAttributeAction extends BuilderAction {
    static id = "setRentalSearchProductAttribute";
    static dependencies = ["cachedModel"];
    getValue({ editingElement }) {
        const productId = editingElement.dataset.productAttribute;
        if (!productId) {
            return undefined;
        }
        return JSON.stringify({ id: parseInt(productId) });
    }
    async load({ value }) {
        if (!value) {
            return;
        }
        value = JSON.parse(value);
        return this.dependencies.cachedModel.ormSearchRead(
            "product.attribute.value",
            [["attribute_id", "=", parseInt(value.id)]],
            []
        );
    }
    apply({ editingElement, value, loadResult }) {
        const productAttributeSearchRentalEl =
            editingElement.querySelector(".product_attribute_search_rental");
        const productAttributeNameEl =
            editingElement.querySelector(".product_attribute_search_rental_name");
        const productAttributeSelectEl =
            editingElement.querySelector(".s_rental_search_select");

        const id = value ? JSON.parse(value).id : "";
        editingElement.dataset.productAttribute = id;

        productAttributeSearchRentalEl.classList.toggle("d-none", !value);
        productAttributeNameEl.id = id;
        productAttributeSelectEl.replaceChildren(this.addOptionToSelect({ id: "", name: _t("All") }));
        if (loadResult) {
            for (const record of loadResult) {
                productAttributeSelectEl.appendChild(this.addOptionToSelect(record));
            }
        }
    }
    /**
     * @param {Object} record
     * @returns {HTMLOptionElement}
     */
    addOptionToSelect(record) {
        const optionEl = document.createElement("option");
        optionEl.value = record.id;
        optionEl.innerText = record.name;
        return optionEl;
    }
}

registry.category("website-plugins").add(RentalSearchOptionPlugin.id, RentalSearchOptionPlugin);
