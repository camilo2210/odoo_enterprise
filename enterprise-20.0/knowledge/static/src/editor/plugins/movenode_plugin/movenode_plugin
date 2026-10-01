import { Plugin } from "@html_editor/plugin";

export class KnowledgeMoveNodePlugin extends Plugin {
    static id = "knowledgeMoveNode";
    /** @type {import("plugins").EditorResources} */
    resources = {
        move_widget_position_processors: (position, movableElement) => {
            if (!movableElement.matches('[data-embedded="view"]')) {
                return position;
            }
            return {
                ...position,
                // Embedded views have a header containing the "New" button. Shift the
                // move widget down so it is vertically centered with that button.
                top: position.top + 15,
                // Embedded views already extend into the editor gutter. Move the widget
                // closer to the view edge so it stays visually aligned with the content.
                left: position.left + 21,
            };
        },
    };
}
