import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { WelcomePage } from "@frontdesk/welcome_page/welcome_page";
import { RegisterPage } from "@frontdesk/register_page/register_page";
import { Navbar } from "@frontdesk/navbar/navbar";
import { EndPage } from "@frontdesk/end_page/end_page";

import { Component, onWillStart, markup, proxy, t, useProps } from "@odoo/owl";

import { isHtmlEmpty } from "@web/core/utils/html";

export class Frontdesk extends Component {
    static template = "frontdesk.Frontdesk";
    static components = {
        WelcomePage,
        Navbar,
        RegisterPage,
        EndPage,
    };

    props = useProps({
        id: t.number(),
        isMobile: t.boolean(),
        currentLang: t.string(),
    });
    setup() {
        this.isHtmlEmpty = isHtmlEmpty;
        this.state = proxy({
            currentComponent: WelcomePage,
        });
        const urlToken = window.location.href.split("/").findLast((s) => s);
        this.token = urlToken.includes("?") ? urlToken.split("?")[0] : urlToken;
        this.frontdeskUrl = `/frontdesk/${this.props.id}/${this.token}`;
        onWillStart(this.onWillStart);
        if (this.props.isMobile) {
            // Retrieve the saved component from sessionStorage
            const savedComponent = sessionStorage.getItem("currentComponent");
            if (savedComponent) {
                const component = registry.category("frontdesk_screens").get(savedComponent);
                this.state.currentComponent = component;
            }
            window.addEventListener("beforeunload", () => {
                // Before the page refresh, save the current component to sessionStorage
                sessionStorage.setItem("currentComponent", this.state.currentComponent.name);
            });
        }
    }

    async onWillStart() {
        this.frontdeskData = await rpc(`${this.frontdeskUrl}/get_frontdesk_data`);
        this.station = this.frontdeskData.station[0];
        // markup: description is coming from HTML field on frontdesk.frontdesk
        this.station.description = this.station.description ? markup(this.station.description) : "";
    }

    /* This method creates the visitor in the backend through rpc call */
    async createVisitor() {
        const result = await rpc(`${this.frontdeskUrl}/prepare_visitor_data`, {
            name: this.visitorData.visitorName,
            phone: this.visitorData.visitorPhone,
            email: this.visitorData.visitorEmail,
            company: this.visitorData.visitorCompany,
            host_id: this.hostData ? this.hostData.hostId : false,
        });
        this.visitorId = result.visitor_id;
    }

    onClose() {
        // Check if the device is mobile or not and show the screen accordingly
        !this.props.isMobile ? this.showScreen("WelcomePage") : this.showScreen("VisitorForm");
    }

    /**
     * @param {Event} ev
     */
    onChangeLang(ev) {
        window.location.href = window.location.pathname + `?lang=${encodeURIComponent(ev.currentTarget.value)}`;
    }

    /**
     * This method change the current screen
     *
     * @param {string} name
     */
    showScreen(name) {
        const component = registry.category("frontdesk_screens").get(name);
        this.state.currentComponent = component;
    }

    /* Reset the data */
    resetData() {
        this.hostData = null;
        this.visitorData = null;
    }

    /**
     * @param {string} name
     * @param {string|false} phone
     * @param {string|false} email
     * @param {string|false} company
     */
    setVisitorData(name, phone, email, company) {
        this.visitorData = {
            visitorName: name,
            visitorPhone: phone,
            visitorEmail: email,
            visitorCompany: company,
        };
    }

    getVisitorData() {
        return this.visitorData;
    }

    /**
     * @param {Object} host
     */
    setHostData(host) {
        this.hostData = {
            hostId: host.id,
            hostName: host.display_name,
        };
    }

    // -------------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------------

    get frontdeskProps() {
        let props = {};
        if (this.state.currentComponent === WelcomePage) {
            props = {
                resetData: this.resetData.bind(this),
                companyName: this.frontdeskData.company.name,
                onChangeLang: this.onChangeLang.bind(this),
                showScreen: this.showScreen.bind(this),
                setVisitorData: this.setVisitorData.bind(this),
                getVisitorData: this.getVisitorData.bind(this),
                visitorData: this.getVisitorData() || false,
                isMobile: this.props.isMobile,
                currentComponent: this.state.currentComponent.name,
                stationInfo: this.station,
                langs: this.frontdeskData.langs.length > 1 ? this.frontdeskData.langs : false,
                currentLang: this.props.currentLang,
                token: this.token,
                setHostData: this.setHostData.bind(this),
                theme: this.station.theme,
            };
        } else if (this.state.currentComponent === RegisterPage) {
            props = {
                showScreen: this.showScreen.bind(this),
                onClose: this.onClose.bind(this),
                createVisitor: this.createVisitor.bind(this),
                theme: this.station.theme,
                isMobile: this.props.isMobile,
                hostData: this.hostData,
            };
        } else if (this.state.currentComponent === EndPage) {
            props = {
                showScreen: this.showScreen.bind(this),
                onClose: this.onClose.bind(this),
                isMobile: this.props.isMobile,
                theme: this.station.theme,
                hostData: this.hostData,
            };
        }
        return props;
    }

    get navBarProps() {
        return {
            showScreen: this.showScreen.bind(this),
            currentComponent: this.state.currentComponent.name,
            companyInfo: this.frontdeskData.company,
            isMobile: this.props.isMobile,
            theme: this.station.theme,
            onChangeLang: this.onChangeLang.bind(this),
            langs: this.frontdeskData.langs.length > 1 ? this.frontdeskData.langs : false,
            currentLang: this.props.currentLang,
        };
    }
}

registry.category("public_components").add("frontdesk", Frontdesk);
