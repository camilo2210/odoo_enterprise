import { WebsiteGeneratorForm } from "@website_generator/client_actions/import_form/import_form";
import { patch } from "@web/core/utils/patch";
import {
    ROUTES,
    Configurator,
    SkipButton,
} from "@website/client_actions/configurator/configurator";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, t, useProps } from "@odoo/owl";
import { WEBSITE_GENERATOR_ROUTE } from "@website_enterprise/client_actions/configurator/configurator";
import { rpc } from "@web/core/network/rpc";

ROUTES.websiteGenerator = WEBSITE_GENERATOR_ROUTE; // TODO: make these urls prettier?

export class WebsiteGeneratorScreen extends WebsiteGeneratorForm {
    static components = { SkipButton };
    static template = "website_generator.Configurator.WebsiteGeneratorScreen";

    screenProps = useProps({
        skip: t.function(),
    });

    setup() {
        super.setup();
        this.state.importWebsite = true;
        this.state.websiteId = this.props.websiteId;
        this.action = useService("action");
        onWillStart(async () => {
            this.state.websiteId = await rpc("/website/get_current_website_id");
        });
    }

    onSubmitted() {
        this.action.doAction({
            type: "ir.actions.act_url",
            url: "/odoo/action-website_generator.website_generator_screen?reload=true",
            target: "self",
        });
    }
}

patch(Configurator, {
    components: {
        ...Configurator.components,
        WebsiteGeneratorScreen,
    },
});

patch(Configurator.prototype, {
    get currentComponent() {
        if (this.state.currentStep === ROUTES.websiteGenerator) {
            return WebsiteGeneratorScreen;
        }
        return super.currentComponent;
    },
});
