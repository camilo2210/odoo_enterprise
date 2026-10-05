import { Component, t, useProps } from "@odoo/owl";

export class Navbar extends Component {
    static template = "frontdesk.Navbar";

    props = useProps({
        companyInfo: t.object(),
        currentComponent: t.string(),
        isMobile: t.boolean(),
        showScreen: t.function(),
        onChangeLang: t.function(),
        theme: t.string(),
        langs: t.or([t.object(), t.boolean()]),
        currentLang: t.string(),
    });
}
