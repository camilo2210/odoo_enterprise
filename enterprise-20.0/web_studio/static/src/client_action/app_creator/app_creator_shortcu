import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const actionRegistry = registry.category("actions");

actionRegistry.add("action_web_studio_app_creator", () => {
    const studio = useService("studio");
    studio.open(studio.MODES.APP_CREATOR);
});
