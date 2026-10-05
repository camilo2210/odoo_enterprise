import { Component, onMounted, onWillUnmount, proxy, signal, t, useProps } from "@odoo/owl";
import { setIntersectionObserver } from "@knowledge/js/knowledge_utils";

export class WithLazyLoading extends Component {
    static template = "knowledge.WithLazyLoading";

    props = useProps({
        slots: t.object(),
    });

    loaderRef = signal.ref();

    setup() {
        this.state = proxy({ isLoaded: false });

        onMounted(() => {
            const el = this.loaderRef();
            this.observer = setIntersectionObserver(el, () => {
                this.state.isLoaded = true;
            });
        });

        onWillUnmount(() => {
            this.observer.disconnect();
        });
    }
}
