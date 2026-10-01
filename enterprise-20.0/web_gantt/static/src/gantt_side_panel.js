import { useDebounced } from "@web/core/utils/timing";
import { Component, signal, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class GanttSidePanel extends Component {
    static template = "web.GanttSidePanel";

    static panelTemplate = "web.GanttSidePanel.Panel";

    props = useProps({
        editRecord: t.any(),
        onResize: t.any(),
        showUnscheduledZone: t.any(),
        model: t.any(),
        width: t.any(),
    });

    rootRef = signal.ref();

    setup() {
        this.debouncedOnInput = useDebounced((width) => {
            this.props.onResize(width);
        }, 100);
    }

    get displayLoadMoreButton() {
        const { eventsToSchedule } = this.props.model.data;
        return eventsToSchedule && eventsToSchedule.records.length < eventsToSchedule.length;
    }

    get toScheduleString() {
        const { eventsToSchedule } = this.props.model.data;
        if (eventsToSchedule.length) {
            return _t("%s to schedule", eventsToSchedule.length);
        }
        return _t("Nothing to schedule");
    }

    /**
     * Handles the resize feature on the sidebar
     *
     * @private
     * @param {PointerEvent} ev
     */
    _onStartResize(ev) {
        // Only triggered by left mouse button
        if (ev.button !== 0) {
            return;
        }

        const initialX = ev.pageX;
        const initialWidth = this.rootRef().offsetWidth;
        const resizeStoppingEvents = ["keydown", "pointerdown", "pointerup"];

        // Pointermove event : resize header
        const resizePanel = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const maxWidth = Math.max(0.5 * window.innerWidth, initialWidth);
            const delta = ev.pageX - initialX;
            const newWidth = Math.min(maxWidth, Math.max(150, initialWidth - delta));
            this.rootRef().style.width = `${newWidth}px`;
            this.debouncedOnInput(newWidth);
        };
        document.addEventListener("pointermove", resizePanel, true);

        // Pointer or keyboard events : stop resize
        const stopResize = (ev) => {
            // Ignores the initial 'left mouse button down' event in order
            // to not instantly remove the listener
            if (ev.type === "pointerdown" && ev.button === 0) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();

            document.removeEventListener("pointermove", resizePanel, true);
            resizeStoppingEvents.forEach((stoppingEvent) => {
                document.removeEventListener(stoppingEvent, stopResize, true);
            });
            // we remove the focus to make sure that the there is no focus inside
            // the panel. If that is the case, there is some css to darken the whole
            // thead, and it looks quite weird with the small css hover effect.
            document.activeElement.blur();
        };
        // We have to listen to several events to properly stop the resizing function. Those are:
        // - pointerdown (e.g. pressing right click)
        // - pointerup : logical flow of the resizing feature (drag & drop)
        // - keydown : (e.g. pressing 'Alt' + 'Tab' or 'Windows' key)
        resizeStoppingEvents.forEach((stoppingEvent) => {
            document.addEventListener(stoppingEvent, stopResize, true);
        });
    }
}
