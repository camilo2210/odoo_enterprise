import { Component, t, useProps, xml } from "@odoo/owl";
import { useSubEnv } from "@web/owl2/utils";

/**
 * Loads the given props to the environment of the nested components.
 *
 * Usage:
 * <WithSubEnv prop1="value1" prop2="value2">
 *    <MyComponent/>
 * </WithSubEnv>
 *
 * MyComponent will then be able to access `prop1` and `prop2` from its environment.
 * (i.e: with `this.env.prop1` and `this.env.prop2`)
 */
export class WithSubEnv extends Component {
    static template = xml`<t t-call-slot="default"/>`;

    props = useProps({
        model: t.object(),
    });

    setup() {
        useSubEnv(this.props);
    }
}
