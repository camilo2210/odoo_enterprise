import { registry } from "@web/core/registry";

export async function buyNumberAfterInstall(env) {
    const phoneNumbersMenu = env.services.menu
        .getAll()
        .find((menu) => menu.xmlid === "voip.voip_did_number_list_menu");
    await env.services.menu.selectMenu(phoneNumbersMenu);
    return "voip.action_voip_did_number_search_wizard";
}

registry.category("actions").add("voip.buy_number_after_install", buyNumberAfterInstall);
