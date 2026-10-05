import { onMounted, onWillUnmount, proxy } from "@odoo/owl";

export const SignDocumentDropZone = (T) =>
    class SignDocumentDropZone extends T {
        setup() {
            super.setup();
            this.dragState = proxy({
                showDragZone: false,
            });
            const highlight = this.highlight.bind(this);
            const unhighlight = this.unhighlight.bind(this);
            const drop = this.onDrop.bind(this);
            onMounted(() => {
                const el = document.querySelector(".o_content");
                if (!el) {
                    return;
                }
                this._contentEl = el;
                el.addEventListener("dragover", highlight);
                el.addEventListener("dragleave", unhighlight);
                el.addEventListener("drop", drop);
            });
            onWillUnmount(() => {
                const el = this._contentEl;
                if (!el) {
                    return;
                }
                el.removeEventListener("dragover", highlight);
                el.removeEventListener("dragleave", unhighlight);
                el.removeEventListener("drop", drop);
            });
        }

        highlight(ev) {
            ev.stopPropagation();
            ev.preventDefault();
            this.dragState.showDragZone = true;
        }

        unhighlight(ev) {
            ev.stopPropagation();
            ev.preventDefault();
            this.dragState.showDragZone = false;
        }

        async onDrop(ev) {
            ev.preventDefault();
            const files = ev.dataTransfer.files;
            const resModel = this.props.list.config.resModel;
            if (files.length) {
                await this.env.bus.trigger("change_file_input", { files, resModel });
            }
            this.dragState.showDragZone = false;
        }
    };
