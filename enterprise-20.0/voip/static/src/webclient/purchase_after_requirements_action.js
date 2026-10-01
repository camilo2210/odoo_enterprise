import { registry } from "@web/core/registry";

export function purchaseAfterRequirements(env, action) {
    return env.services.orm.call("voip.did.number.search.wizard", "action_purchase", [
        action.params.wizard_id,
    ]);
}

registry.category("actions").add("voip.purchase_after_requirements", purchaseAfterRequirements);
