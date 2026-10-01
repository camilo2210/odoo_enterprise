import "@ai/client_tools";
import { aiClientToolsRegistry } from "@ai/discuss/core/common/ai_client_tool_registry";
import { getData } from "@ai/utils/bus_data_getter";

aiClientToolsRegistry.add("finalize_website_page", async (thread, params) => {
    const page = await getData("aiWebsitePage");
    const report = await page.finalizePage(params.html, params.other_actions, params.target_page);
    return { note: params.note, actions: report };
});

// The default `reload` re-inits the whole website builder action, which bounces
// the user back to the homepage. Inside the builder, reload the editor in place.
const defaultReload = aiClientToolsRegistry.get("reload");
aiClientToolsRegistry.add(
    "reload",
    async (thread, params) => {
        const env = thread?.store?.env;
        if (!env?.services?.website?.currentWebsite) {
            return defaultReload(thread, params);
        }
        env.bus.trigger("RELOAD_EDITOR", { save: false });
    },
    { force: true },
);
