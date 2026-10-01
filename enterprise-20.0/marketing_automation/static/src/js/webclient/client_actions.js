import { registry } from "@web/core/registry";

async function saveAndBack(env) {
    const actionService = env.services.action;
    await actionService.restore(actionService.currentController.config.breadcrumbs.at(-2).jsId);
}

registry.category("actions").add("marketing_automation.save_and_back", saveAndBack);
