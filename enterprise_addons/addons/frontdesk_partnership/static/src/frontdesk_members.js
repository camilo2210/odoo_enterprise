import { registry } from "@web/core/registry";
import { WelcomePageMembers } from "./welcome_page/welcome_page_members";
import { Frontdesk } from "@frontdesk/frontdesk";
import { t, useProps } from "@odoo/owl";

export class FrontdeskMembers extends Frontdesk {
    static template = "frontdesk_partnership.FrontdeskMembers";
    static components = {
        ...Frontdesk.components,
        WelcomePageMembers,
    };

    // `props` is inherited from Frontdesk untouched — this only covers the addition.
    extraProps = useProps({
        frontdeskType: t.string(),
    });

    setup() {
        super.setup();
        if (this.extraProps.frontdeskType == "members") {
            this.state.currentComponent = WelcomePageMembers;
        }
    }

    onClose() {
        if (this.props.isMobile) {
            this.showScreen("VisitorForm");
        } else {
            !this.frontdeskType === "members"
                ? this.showScreen("WelcomePage")
                : this.showScreen("WelcomePageMembers");
        }
    }

    get frontdeskProps() {
        let props = super.frontdeskProps;
        if (!Object.keys(props).length && this.state.currentComponent === WelcomePageMembers) {
            props = {
                showScreen: this.showScreen.bind(this),
                resetData: this.resetData.bind(this),
                onChangeLang: this.onChangeLang.bind(this),
                token: this.token,
                companyName: this.frontdeskData.company.name,
                stationInfo: this.station,
                langs: this.frontdeskData.langs.length > 1 ? this.frontdeskData.langs : false,
                currentLang: this.props.currentLang,
                setVisitorData: this.setVisitorData.bind(this),
                createVisitor: this.createVisitor.bind(this),
            };
        }
        return props;
    }
}

registry.category("public_components").add("frontdesk_members", FrontdeskMembers);
