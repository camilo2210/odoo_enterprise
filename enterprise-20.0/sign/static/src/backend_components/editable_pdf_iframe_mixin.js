import { renderToString } from "@web/core/utils/render";
import {
    startHelperLines,
    normalizePosition,
    generateRandomId,
    edgeScrollStep,
    startEdgeScroll,
    getOffsetFromIframe,
    startResize,
    getIframeViewerContainer,
} from "@sign/components/sign_request/utils";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { setRecurringAnimationFrame } from "@web/core/utils/timing";

/**
 * Mixin that adds edit features into PDF_iframe classes like drag/drop, resize, helper lines
 * Currently, it should be used only for SignTemplateIframe
 * Parent class should implement allowEdit and saveChanges
 *
 * @param { class } pdfClass
 * @returns class
 */
export const EditablePDFIframeMixin = (pdfClass) =>
    class extends pdfClass {
        /**
         * @override
         */
        async start() {
            await super.start();
            this.root.addEventListener("keydown", (e) => this.handleKeyDown(e));
            const validator = {
                set: this.onSignItemsSet.bind(this),
                deleteProperty: this.onSignItemsDelete.bind(this),
            };
            for (const page in this.signItems) {
                this.signItems[page] = new Proxy(this.signItems[page], validator);
                for (const signItem of Object.values(this.signItems[page])) {
                    if (signItem.data.type === "signature") {
                        this.setSignatureImage(signItem, signItem.data.roleName);
                    } else if (signItem.data.type === "initial") {
                        this.setSignatureImage(signItem, this.getInitialsText(signItem.data.roleName));
                    }
                }
            }
            this.updateSideBarSignItemsCount();
        }

        onSignItemsSet(target, key, value) {
            target[key] = value;
            const roleName = value.data.roleName;
            if (value.data.type === "signature") {
                this.setSignatureImage(value, roleName);
            } else if (value.data.type === "initial") {
                this.setSignatureImage(value, this.getInitialsText(roleName));
            }
            this.updateSideBarSignItemsCount();
            return true;
        }

        onSignItemsDelete(target, key) {
            delete target[key];
            this.updateSideBarSignItemsCount();
            return true;
        }

        /**
         * Gets an SVG matching the given parameters, output compatible with the
         * src attribute of <img/>.
         *
         * @param {string} text: the name to draw
         * @param {number} width: the width of the resulting image in px
         * @param {number} height: the height of the resulting image in px
         * @returns {string} image = mimetype + image data
         */
        getSVGText(text="", width, height) {
            const svg = renderToString("web.sign_svg_text", {
                width: width,
                height: height,
                font: this.font,
                text: text,
                type: "signature",
                color: "DarkBlue",
            });
            return "data:image/svg+xml," + encodeURI(svg);
        }

        setSignatureImage(signItem, text) {
            const { data, el } = signItem;
            const width = this.getPageContainer(data.page).getBoundingClientRect().width * data.width;
            const height = this.getPageContainer(data.page).getBoundingClientRect().height * data.height;
            const src = this.getSVGText(text, width, height);
            this.fillItemWithSignature(el.firstChild.firstChild, src);
        }

        updateRoleName(roleId, roleName) {
            for (const page in this.signItems) {
                for (const id in this.signItems[page]) {
                    const signItem = this.signItems[page][id];
                    if (signItem.data.responsible === roleId) {
                        signItem.data.roleName = roleName;
                        if (signItem.data.type === "signature") {
                            this.setSignatureImage(signItem, roleName);
                        } else if (signItem.data.type === "initial") {
                            this.setSignatureImage(signItem, this.getInitialsText(roleName));
                        }
                    }
                }
            }
        }

        /**
         * Return the initials string format for a given text.
         * @param {string} text: the name that will be turned into initials
         * @param {string}: text in initials format, such as "G.F."
         */
        getInitialsText(text) {
            const parts = text.split(' ');
            const initials = parts.map(part => {
                return part.length > 0 ? part[0] + '.' : '';
            });
            return initials.join('');
        }

        updateSideBarSignItemsCount() {
            this.signItemsCountByRole = {};
            const countedRadioSets = {};
            for (const page in this.signItems) {
                for (const id in this.signItems[page]) {
                    const { data } = this.signItems[page][id];
                    if (data.type === "radio") {
                        if (countedRadioSets[data.radio_set_id]) {
                            continue;
                        }
                        countedRadioSets[data.radio_set_id] = true;
                    }
                    const role = this.signItems[page][id].data.responsible;
                    if (!this.signItemsCountByRole[role]) {
                        this.signItemsCountByRole[role] = 0;
                    }
                    this.signItemsCountByRole[role]++;
                }
            }
            this.props.updateSignItemsCountCallback();
        }

        setFont(font) {
            this.font = font;
        }

        /**
         * Callback executed when a sign item is resized
         * @param {SignItem} signItem
         * @param {Object} change object with new width and height of sign item
         * @param {Boolean} end boolean indicating if the resize is done or still in progress
         */
        onResizeItem(signItem, change, end = false) {
            this.setCanvasVisibility("hidden");
            this.helperLines.show(signItem.el);
            /**
             * Apply the changes only if they respect the minimum width/height.
             * The minimum width is 5.5% of the page width
             * The minimum height is 1% of the page height
             */
            if (change.width >= 0.01 && change.height >= 0.01) {
                const signItemIds = signItem.data.type === "radio" ? this.radioSets[signItem.data.radio_set_id].radio_item_ids : [signItem.data.id];
                for (const id of signItemIds) {
                    const signItem = this.getSignItemById(id);
                    if (!signItem) {
                        continue;
                    }
                    Object.assign(signItem.el.style, {
                        height: `${change.height * 100}%`,
                        width: `${change.width * 100}%`,
                    });
                    Object.assign(this.getSignItemById(signItem.data.id).data, {
                        width: change.width,
                        height: change.height,
                        updated: true,
                    });
                    this.updateSignItemFontSize(signItem);
    
                    if (signItem.data.type === "signature") {
                        this.setSignatureImage(signItem, signItem.data.roleName);
                    } else if (signItem.data.type === "initial") {
                        this.setSignatureImage(signItem, this.getInitialsText(signItem.data.roleName));
                    }
                }
            }
            if (end) {
                this.helperLines.hide();
                this.setCanvasVisibility("visible");
                this.setTemplateChanged();
            }
        }

        get allowEdit() {
            return false;
        }

        getSignItemById(id) {
            for (const page in this.signItems) {
                if (this.signItems[page].hasOwnProperty(id)) {
                    return this.signItems[page][id];
                }
            }
            return undefined;
        }

        /**
         * Changes visibility of the canvas_layer_0 that is used for drawing connecting lines between sign items of type radio.
         * @param {string} visibility
         */
        setCanvasVisibility(visibility) {
            const canvas_layer = this.getPageContainer(1).parentElement.parentElement.querySelector("#canvas_layer_0");
            if(canvas_layer){
                canvas_layer.style.visibility = visibility;
            }
        }

        /**
         * Returns the position of mouse pointer inside the iframe viewer
         * @param {mouseX} clientX 
         * @param {mouseY} clientY 
         * @returns 
         */
        getMousePositionInViewerContainer(clientX, clientY) {
            const rect = this.viewerContainer.getBoundingClientRect();
            const {scrollTop, scrollLeft} = this.viewerContainer;

            const mousePosition = {
                x: (clientX - rect.left) + scrollLeft,
                y: (clientY - rect.top) + scrollTop
            }

            return mousePosition;
        }

        /**
         * Attaches event listeners to a sign item to enable and manage dragging,
         * multi-dragging, and resizing interactions.
         *
         * @param {Object} signItem - The sign item object to which the interactions will be attached.
        */
        startSignItemInteractions(signItem) {
            // Add listeners to enable multi-dragging functionality
            const handle = signItem.el.querySelector(".o_sign_config_handle");
            handle.setAttribute("draggable", true);
            handle.addEventListener("dragstart", (e) => this.onMultiDragStart(e));
            handle.addEventListener("dragend", (e) => this.onMultiDragEnd(e));
        }

        /**
         * Adds event listeners to the viewer container and pages
         * to support multi-drag and multi-select functionality.
        */
        startMultiDragAndDrop() {
            this.viewerContainer = getIframeViewerContainer(this);
            this.viewerContainer.addEventListener('mousedown', (e) => this.onMultiSelectMouseDown(e));
            this.root.querySelectorAll(".page").forEach((page) => {
                if (!page.hasAttribute("updated")) {
                    page.addEventListener("dragover", (e) => this.onMultiDragOver(e));
                    page.addEventListener("drop", (e) => this.handleMultiItemDrop(e));
                    page.setAttribute("updated", true);
                }
            });
        }

        /**
         * Handles the mouse down event
         * It handles the selection rectangle drawing start
         * @param {MouseEvent} e
        */
        onMultiSelectMouseDown(e) {
            const isInSelectedElement = this.selectedElements?.some(element => element.el.contains(e.target));
            if (isInSelectedElement) {
                return; // return in case it's the starting of multiDragging
            } 

            /**
             * Only allow drawing the selection rectangle in empty spaces
             * where the cursor is auto and the left button is pressed.
            */
            const cursorStyle = window.getComputedStyle(e.target)["cursor"];
            const cursorButton = e.button;
            if (cursorButton !== 0 || cursorStyle !== 'auto') {
                return;
            }

            e.preventDefault();
            this.resetSelection(); // Reset selection in case the event was triggered by a mouse click

            // Disable text selection while dragging to create selection rectangle
            this.viewerContainer.style.userSelect = 'none';

            // Start the selection rectangle drawing process
            this.mousePosition = this.getMousePositionInViewerContainer(e.clientX, e.clientY);
            this.startPos = this.mousePosition;
            this.isMultiSelecting = true;
            this.selectionAnimationFrameCancel = setRecurringAnimationFrame(this.updateSelectionRect.bind(this));
            this.updateSelectionRect();

            const onMouseMove = (e) => this.onMultiSelectMouseMove(e);
            this.viewerContainer.addEventListener('mousemove', onMouseMove);

            // Trigger multiSelect termination on mouseup, blur, and mouse leave
            const multiSelectEndingEvents = ["mouseup", "blur", "mouseleave", "contextmenu"];
            const onMultiSelectEnd = (e) => this.onMultiSelectEnd(e);
            multiSelectEndingEvents.forEach(eventType => this.viewerContainer.addEventListener(eventType, onMultiSelectEnd));

            this.multiSelectCleanups = []; // cleanup functions to be called at the end of multi selection
            this.multiSelectCleanups.push(() => {
                this.viewerContainer.style.userSelect = '';
                this.startPos = null;
                this.isMultiSelecting = false;
                this.viewerContainer.removeEventListener('mousemove', onMouseMove);
                multiSelectEndingEvents.forEach(eventType => this.viewerContainer.removeEventListener(eventType, onMultiSelectEnd));
                // Clear the canvas to remove the selection rectangle.
                // Then refresh the sign items to redraw any other persistent drawings,
                // such as the radio button line in between them.
                // TODO: Optimize in the future to support multiple drawing canvases
                this.clearCanvas();
                this.refreshSignItems();
            });
        }

        /**
         * Handles the mouse move event
         * It updates the mouse position and keeps track of the selection rectangle
         * It also handles the auto scroll if selection occurs in multiple pages
         * @param {MouseEvent} e
        */
        onMultiSelectMouseMove(e) {
            if (this.isMultiSelecting) {
                e.preventDefault();
                this.mousePosition = this.getMousePositionInViewerContainer(e.clientX, e.clientY);
                const mouseIframeOffset = getOffsetFromIframe(
                    document.querySelector(".o_sign_documents_container"), 
                    e.clientX, 
                    e.clientY
                );
                edgeScrollStep(
                    this.root.querySelector('#viewerContainer'), 
                    mouseIframeOffset, 
                    {boundary: 0.15, maxDragAmount: 25}
                ); // Manually scroll the viewer container
            }
        }

        /**
         * Handles the mouse up event if dragging is in progress
         * It stops the selection rectangle drawing process
         * It updates the list of selected elements and clears the canvas
        */
        onMultiSelectEnd() {
            if (this.isMultiSelecting) {
                this.updateSelectedElementsList();
                while (this.multiSelectCleanups?.length) {
                    this.multiSelectCleanups.pop()();
                }
            }
        }

        /**
         * Clears the canvas
         * It sets the zIndex back to 1
        */
        clearCanvas() {
            const canvas = this.getCanvas();
            canvas.style.zIndex = 1;
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }

        /**
         * Recursively updates the selection rectangle until the mouse is released
        */
        updateSelectionRect() {
            if (this.isMultiSelecting) {
                this.drawSelectionRect();
            }
        }

        /**
         * Resets the selection
         * It removes the multi_selected class from the selected elements and get them unfocused.
         * It clears the multiDragState and empty the selectedElements list.
        */
        resetSelection() {
            this.selectedElements?.forEach(element => {
                element.el.classList.remove('multi_selected');
                element.el.blur();
            });
            this.selectedElements = [];
            this.multiDragState = null;
        }

        /**
         * Draws the selection rectangle on the canvas layer
         * The zIndex is set to a high value to make it visible above other elements
        */
        drawSelectionRect() {
            this.clearCanvas();
            const canvas = this.getCanvas();
            const ctx = canvas.getContext('2d');

            // Normalize mouse coordinates to canvas space
            const scale = this.getCanvasScale();
            const startX = this.startPos.x / scale;
            const startY = this.startPos.y / scale;
            const mouseX = this.mousePosition.x / scale;
            const mouseY = this.mousePosition.y / scale;
            const width = mouseX - startX;
            const height = mouseY - startY;

            canvas.style.position = 'absolute';
            canvas.style.zIndex = 100;
            ctx.strokeStyle = 'rgba(89, 105, 196, 0.35)';
            ctx.fillStyle = 'rgba(89, 105, 196, 0.1)';
            ctx.lineWidth = 1;
            ctx.setLineDash([]);
            ctx.fillRect(startX, startY, width, height);
            ctx.strokeRect(startX, startY, width, height);
        }

        /**
         * Returns the selection rectangle
        */
        getSelectionRect() {
            const x = Math.min(this.startPos.x, this.mousePosition.x);
            const y = Math.min(this.startPos.y, this.mousePosition.y);
            const width = Math.abs(this.mousePosition.x - this.startPos.x);
            const height = Math.abs(this.mousePosition.y - this.startPos.y);
            return { x, y, width, height };
        }

        /**
         * Checks if two rectangles intersect
         * @param {Object} rect1 - First rectangle with left, right, top, bottom properties
         * @param {Object} rect2 - Second rectangle with x, y, width, height properties
         * @returns {boolean} - True if the rectangles intersect, false otherwise
         */
        doRectanglesIntersect(rect1, rect2) {
            return !(rect1.left > rect2.x + rect2.width ||
                    rect1.right < rect2.x ||
                    rect1.top > rect2.y + rect2.height ||
                    rect1.bottom < rect2.y);
        }

        /**
         * Checks if an element intersects with the selection rectangle
         * @param {Element} element - The sign element to check
         * @param {Object} selectionRect - The selection rectangle with x, y, width, height properties
         * @returns {boolean} - True if the element intersects the selection rectangle, false otherwise
         */
        getElementIntersectsSelection(element, selectionRect) {
            const elemRect = element.getBoundingClientRect();
            const containerRect = this.viewerContainer.getBoundingClientRect();
            const {scrollTop, scrollLeft} = this.viewerContainer;
            // Convert element coordinates to be relative to the container including scroll position
            const elem = {
                left: elemRect.left - containerRect.left + scrollLeft,
                top: elemRect.top - containerRect.top + scrollTop
            };
            elem['right'] = elem['left'] + elemRect.width;
            elem['bottom'] = elem['top'] + elemRect.height;
            return this.doRectanglesIntersect(elem, selectionRect);
        }

        /**
         * Updates the list of selected elements based on the current selection rectangle
         * The list is updated by adding the sign elements that intersect the selection rectangle
        */
        updateSelectedElementsList() {
            const signElements = this.root.querySelectorAll('.o_sign_sign_item');
            const selectionRect = this.getSelectionRect();
            signElements?.forEach(element => {
                const {id} = element.dataset;
                const signItem = this.getSignItemById(id);
                /* Only add elements to selection if they intersect with the selection rectangle
                and are not already in the selection list */
                if (this.getElementIntersectsSelection(element, selectionRect) &&
                    !this.selectedElements?.some(item => item.data.id === id)) {
                    this.selectedElements.push(signItem);
                    element.classList.add('multi_selected');
                }
            });

            // Focus at least the first selected element to ensure keyboard events work.
            if (this.selectedElements.length > 0) {
                this.selectedElements[0].el.focus();
            }
        }

        /**
         * Given the (x, y) position with respect to the viewer container
         * @param {Number} x - x position relative to the viewer container (including scroll)
         * @param {Number} y - y position relative to the viewer container (including scroll)
         * @returns the document page which contain the (x, y) position
         * and the ratio of the (x, y) position inside the page.
         */
        getPositionData(x, y, itemWidth = 0, itemHeight = 0) {
            const viewerContainer = this.viewerContainer || getIframeViewerContainer(this);

            for (let page = 1; page <= this.pageCount; page++) {
                const pageElement = this.getPageContainer(page);
                const pageRect = pageElement.getBoundingClientRect();
                const viewerRect = viewerContainer.getBoundingClientRect();

                // Convert page position to be relative to the viewer container
                const pageLeft = pageRect.left - viewerRect.left + viewerContainer.scrollLeft;
                const pageTop = pageRect.top - viewerRect.top + viewerContainer.scrollTop;
                const pageRight = pageLeft + pageRect.width;
                const pageBottom = pageTop + pageRect.height;

                if (pageLeft <= x && x+itemWidth <= pageRight && pageTop <= y && y+itemHeight <= pageBottom) {
                    const width = pageRect.width;
                    const height = pageRect.height;
                    const x1 = x - pageLeft;
                    const y1 = y - pageTop;
                    const posX = x1 / width;
                    const posY = y1 / height;
                    return {
                        page: page,
                        posX: posX,
                        posY: posY,
                    };
                }
            }
            return {page: -1};
        }

        /**
         * Handles the copy event for multiple sign items
         * It copies the selected elements to the clipboard
         * It shows a notification to the user
        */
        onCopyItems() {
            if (!this.selectedElements) {
                return;
            }
            this.copiedItems = [];
            this.selectedElements.forEach(element => {
                this.copiedItems.push({...element.data});
            });
            this.notification.add(_t("Sign Items Copied"), {type: "success"});
        }

        /**
         * Handles the paste event
         * It creates new radio sets and maps old IDs to new ones
         * It gets the position data of the mouse with respect to the viewer container to
         * determine the target page and position for the pasted items
         * It adjusts the base position of the copied items to ensure they stay within the page bounds
        */
        async onPasteItems() {
            // Get the target page and position to paste the items
            const {page: targetPage, posX: baseX, posY: baseY} = this.getPositionData(
                this.mousePosition.x,
                this.mousePosition.y
            );
            // If the target page is not found, return
            if (targetPage === -1) {
                return;
            }

            // Create new radio sets and map old IDs to new ones
            const radioSetIdMapping = new Map();
            const uniqueRadioSets = new Set(
                this.copiedItems
                    .filter(item => item.type === 'radio')
                    .map(item => item.radio_set_id)
            );
            for (const oldRadioSetId of uniqueRadioSets) {
                const [newRadioSetId] = await this.orm.create('sign.item.radio.set', [{}]);
                radioSetIdMapping.set(oldRadioSetId, newRadioSetId);
                this.radioSets[newRadioSetId] = {
                    num_options: this.radioSets[oldRadioSetId].num_options,
                    radio_item_ids: [],
                };
            }
           // Find smallest box that contains all copied items
            const bounds = this.copiedItems.reduce((acc, item) => {
                acc.minX = Math.min(acc.minX, item.posX);
                acc.maxX = Math.max(acc.maxX, item.posX + item.width);
                acc.minY = Math.min(acc.minY, item.posY);
                acc.maxY = Math.max(acc.maxY, item.posY + item.height);
                return acc;
            }, { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });

            const boxWidth = bounds.maxX - bounds.minX;
            const boxHeight = bounds.maxY - bounds.minY;

            /* Adjust the base paste positions to ensure all items stay within the page. The
            center of the bounding box can be at most 1 - boxWidth/2 from the left edge.
            and at most 1 - boxHeight/2 from the top edge. */
            const adjustedBaseX = Math.min(Math.max(baseX, boxWidth/2), 1 - boxWidth/2);
            const adjustedBaseY = Math.min(Math.max(baseY, boxHeight/2), 1 - boxHeight/2);

            // Calculate offset to move items as a group to the adjusted position
            const centerOffsetX = adjustedBaseX - (bounds.minX + boxWidth/2);
            const centerOffsetY = adjustedBaseY - (bounds.minY + boxHeight/2);

            // Create new items with adjusted positioning
            for (const data of this.copiedItems) {
                const newItemData = { ...data };
                const id = generateRandomId();
                // Apply the calculated offset to maintain relative positions
                const newPosX = data.posX + centerOffsetX;
                const newPosY = data.posY + centerOffsetY;

                Object.assign(newItemData, {
                    id,
                    page: targetPage,
                    posX: newPosX,
                    posY: newPosY,
                    updated: true,
                });
                // Handle special case for radio buttons to maintain grouping
                if (data.type === 'radio') {
                    const newRadioSetId = radioSetIdMapping.get(data.radio_set_id);
                    newItemData.radio_set_id = newRadioSetId;
                    this.radioSets[newRadioSetId].radio_item_ids.push(id);
                }

                // Add the new item to the page and render it
                this.signItems[targetPage][id] = {
                    data: newItemData,
                    el: this.renderSignItem(newItemData, this.getPageContainer(targetPage)),
                };
            }
            this.setTemplateChanged();
            this.refreshSignItems();

            // Slightly offset the mouse position for subsequent paste operations
            this.mousePosition.x += 10;
            this.mousePosition.y += 10;
        }

        /**
         * Handles the key down event
         * It handles the copy, paste and delete events
         * @param {KeyboardEvent} event
        */
        handleKeyDown(event) {
            if ((event.ctrlKey || event.metaKey) && event.key == 'c' && this.selectedElements) {
                this.onCopyItems();
            } else if ((event.ctrlKey || event.metaKey) && event.key == 'v' && this.copiedItems) {
                this.onPasteItems();
            } else if (event.key === "Delete" && this.selectedElements) {
                this.deleteSignItems(this.selectedElements);
                this.resetSelection();
            }
        }

        renderSignItems() {
            super.renderSignItems();
            if (this.allowEdit) {
                this.startMultiDragAndDrop();
                this.helperLines = startHelperLines(this.root);
            }
        }

        /**
         * Updates the position and page of a sign item in the PDF frame
         * @param {Object} signItem - The sign item object to update
         * @param {Object} positionContext - The position and page data
         * @param {number} positionContext.posX - The new horizontal position
         * @param {number} positionContext.posY - The new vertical position
         * @param {number} positionContext.targetPage - The page number where the item should be placed
         * @param {number} positionContext.initialPage - The original page number of the item
         * @param {HTMLElement} positionContext.page - The DOM element of the target page
        */
        updateSignItemPosition(signItem, positionContext) {
            const { posX, posY, targetPage, initialPage, page } = positionContext;
            const signItemEl = signItem.el;
            if (initialPage !== targetPage) {
                signItem.data.page = targetPage;
                this.signItems[targetPage][signItem.data.id] = signItem;
                delete this.signItems[initialPage][signItem.data.id];

                // Check if the parent element exists before removing the sign element,
                // since the parent page might not be loaded due to iframe lazy loading.
                if (signItemEl.parentElement && signItemEl.parentElement.contains(signItemEl)) {
                    signItemEl.parentElement.removeChild(signItemEl);
                }

                page.appendChild(signItemEl);
            }
            Object.assign(signItem.data, {
                posX,
                posY,
                updated: true,
            });
            Object.assign(signItemEl.style, {
                top: `${posY * 100}%`,
                left: `${posX * 100}%`,
                visibility: "visible",
            });
        }

        /**
         * Queues a page to be refreshed later.
         *
         * This method ensures that the `pagesToRefresh` list is initialized
         * if it hasn't been already, then appends the given page to the list.
         * These pages are typically refreshed as part of a batch operation
         * to update their sign item positions.
         *
         * @param {Object} page - The page object to be marked for refresh.
        */
        markPageForItemPositionRefresh(page) {
            if (!this.pagesToRefreshPositions) {
                this.pagesToRefreshPositions = [];
            }
            this.pagesToRefreshPositions.push(Number(page.dataset.pageNumber));
        }

        /**
         * Refreshes the positions of sign items on all pages marked for refresh.
         * Typically called after layout changes or cleanup operations.
         *
         * @returns {void}
        */
        refreshSignItemPositions() {
            while (this.pagesToRefreshPositions && this.pagesToRefreshPositions.length) {
                const itemsToUpdate = this.signItems[this.pagesToRefreshPositions.pop()];
                if (itemsToUpdate) {
                    Object.values(itemsToUpdate).forEach(signItem => {
                        if (signItem && signItem.el && signItem.data) {
                            const { posX, posY } = signItem.data;
                            const element = signItem.el;
                            element.style.top = `${posY * 100}%`;
                            element.style.left = `${posX * 100}%`;
                        }
                    });
                }
            }
        }

        /**
         * finds the page number of the passed sign item
         * @param {Set} targetItem 
         * @returns page number of passed sign item
         */
        findPageForSignItem(targetItem) {
            for (const [page, items] of Object.entries(this.signItems)) {
                for (const item of Object.values(items)) {
                    if (item === targetItem) {
                        return page;
                    }
                }
            }

            return null; // not found
        }

        /**
         * Starts multi-drag for selected elements
         * @param {MouseEvent} e - The mouse drag event
        */
        startMultiDrag(e) {
            // Store initial state for all selected items
            this.multiDragState = {
                items: this.selectedElements.map(signItem => {
                    const ItemRect = signItem.el.getBoundingClientRect();
                    const pageNumber = 
                        Number(signItem.el.parentElement.dataset.pageNumber) 
                        || this.findPageForSignItem(signItem); // In case the element’s page is not rendered yet (iframe uses lazy loading)
                    const offsetX = e.clientX - ItemRect.left;
                    const offsetY = e.clientY - ItemRect.top;
                    return {
                        signItem,
                        pageNumber: pageNumber,
                        offsetX: offsetX,
                        offsetY: offsetY
                    };
                }),
            };

            // Create composite drag image container
            const dragContainer = document.createElement('div');
            Object.assign(dragContainer.style, {
                position: 'fixed',
                pointerEvents: 'none',
                zIndex: '1000',
                opacity: '0.8'
            });

            // Get the bounding box of all selected elements
            const bounds = this.selectedElements.reduce((acc, item) => {
                const rect = item.el.getBoundingClientRect();
                acc.left = Math.min(acc.left, rect.left);
                acc.top = Math.min(acc.top, rect.top);
                acc.right = Math.max(acc.right, rect.right);
                acc.bottom = Math.max(acc.bottom, rect.bottom);
                return acc;
            }, { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity });

            // Set container dimensions
            dragContainer.style.width = `${bounds.right - bounds.left}px`;
            dragContainer.style.height = `${bounds.bottom - bounds.top}px`;

            // Create clones of selected elements
            this.selectedElements.forEach(item => {
                const itemRect = item.el.getBoundingClientRect();
                const clone = item.el.cloneNode(true);
                clone.style.position = 'absolute';
                clone.style.left = `${itemRect.left - bounds.left}px`;
                clone.style.top = `${itemRect.top - bounds.top}px`;
                clone.style.width = `${itemRect.width}px`;
                clone.style.height = `${itemRect.height}px`;
                clone.style.margin = '0';
                clone.style.cursor = 'grabbing';
                dragContainer.appendChild(clone);
            });

            document.body.appendChild(dragContainer);

            // Calculate offset from cursor to container top-left corner
            const cursorOffsetX = e.clientX - bounds.left;
            const cursorOffsetY = e.clientY - bounds.top;
            e.dataTransfer.setDragImage(dragContainer, cursorOffsetX, cursorOffsetY);

            // Clean up the temporary drag image container after drag starts
            // and hide the original elements
            requestAnimationFrame(() => {
                document.body.removeChild(dragContainer);
                this.selectedElements.forEach(item => item.el.style.visibility = 'hidden');
            });

            this.mouseOffset = {x: 0, y: 0};
            this.scrollCleanup = startEdgeScroll(this.root.querySelector('#viewerContainer'), this.mouseOffset);
            this.isMultiDrag = true;
        }

        onMultiDragStart(e) {
            this.setCanvasVisibility("hidden");
            const signElement = e.currentTarget.parentElement.parentElement.parentElement;
            const isSelectedItemDrag = this.selectedElements?.some(item => item.el === signElement);

            /* If the sign element is picked up and there are selected elements,
            then start multi-drag */
            if (isSelectedItemDrag && this.selectedElements.length > 0) {
                this.startMultiDrag(e);
            } else {
                e.preventDefault(); // prevent default so it doesn't intercept the dragging framework in case there is no selected elements to be dragged
            }
        }

        onMultiDragOver(e) {
            e.preventDefault();
            if (!this.isMultiDrag || !this.multiDragState) return;

            // Update the mouseIframeOffset object to trigger edge scrolling based on the new mouse position
            const mouseIframeOffset = getOffsetFromIframe(
                document.querySelector(".o_sign_documents_container"), 
                e.clientX, 
                e.clientY
            );
            this.mouseOffset.x = mouseIframeOffset.x;
            this.mouseOffset.y = mouseIframeOffset.y;

            e.dataTransfer.dropEffect = "move";
        }

        /**
         * Ends the drag operation
         * @param {MouseEvent} e - The mouse drag end event
        */
        onMultiDragEnd(e) {
            if (!this.isMultiDrag) return;

            this.isMultiDrag = false;
            this.scrollCleanup();
            // Make sign item visible again after dragging ends. It is a mandatory step when
            // moving items out of bounds since in that flow the items don't get re-rendered.
            if (this.selectedElements) {
                this.selectedElements.forEach(item => item.el.style.visibility = 'visible');
            }
            let signItem = e.currentTarget.parentElement.parentElement.parentElement;
            if (signItem)
                signItem.style.visibility = "visible";
            this.setCanvasVisibility("visible");
        }

        /**
         * Handles the multi-item drop event
         * @param {MouseEvent} e - The mouse event
         */
        handleMultiItemDrop(event) {
            event.preventDefault();
            // Stop event propagation to prevent dragged elements from being dropped on parent elements,
            // since the native drop API is used.
            event.stopPropagation();

            if (!this.isMultiDrag || !this.multiDragState) return;

            // First check if all items can be properly dropped
            const dropPositions = [];
            let allItemsCanBeDropped = true;

            this.multiDragState.items.forEach(item => {
                const viewerRect = this.viewerContainer.getBoundingClientRect();
                const mouseX = event.clientX - viewerRect.left + this.viewerContainer.scrollLeft;
                const mouseY = event.clientY - viewerRect.top + this.viewerContainer.scrollTop;

                const {width, height} = item.signItem.el.getBoundingClientRect();
                const itemX = mouseX - item.offsetX;
                const itemY = mouseY - item.offsetY;

                // Determine exact page and position
                const positionData = this.getPositionData(itemX, itemY, width, height);

                // If any item would be dropped outside a valid page area, no drop is allowed
                if (positionData.page === -1) {
                    allItemsCanBeDropped = false;
                }

                dropPositions.push({
                    item: item,
                    positionData: positionData
                });
            });

            if (allItemsCanBeDropped) {
                // Update all items' positions
                dropPositions.forEach(({item, positionData}) => {
                    const signItem = item.signItem;
                    const initialPage = item.pageNumber;
                    const actualTargetPage = positionData.page;
                    const actualPage = this.getPageContainer(actualTargetPage);

                    const positionContext = {
                        posX: positionData.posX,
                        posY: positionData.posY,
                        targetPage: actualTargetPage,
                        initialPage,
                        page: actualPage
                    };
                    this.updateSignItemPosition(signItem, positionContext);
                });
            }

            this.multiDragState = null;
            this.helperLines?.hide();

            this.setTemplateChanged();
            this.refreshSignItems();
        }

        dropSignItem(element, page, pageX, pageY) {
            const textLayer = page.querySelector(".textLayer");
            const targetPage = Number(page.dataset.pageNumber);
            const itemTypeId = element.dataset.itemTypeId;
            const roleId = element.dataset.roleId;
            const roleName = element.dataset.roleName;
            const box = textLayer.getBoundingClientRect();
            const height = box.bottom - box.top;
            const width = box.right - box.left;
            if (itemTypeId) { // new sign element
                const id = generateRandomId();
                const data = this.createSignItemDataFromType({ itemTypeId, roleId, roleName });
                const posX =
                    Math.round(normalizePosition(pageX / width, data.width) * 1000) /
                    1000;
                const posY =
                    Math.round(normalizePosition(pageY / height, data.height) * 1000) /
                    1000;
                Object.assign(data, { id, posX, posY, page: targetPage });
                if (data.type === "initial") {
                    if (this.pageCount > 1) {
                        return this.openDialogAfterInitialDrop(data);
                    }
                } else if (data.type == "radio") {
                    return this.addRadioSet(data);
                }
                this.signItems[targetPage][id] = {
                    data,
                    el: this.renderSignItem(data, page),
                };
            } else if (element.dataset.pageNumber && element.dataset.id) { // repositioning an existing sign element
                const initialPage = Number(element.dataset.pageNumber);
                const id = Number(element.dataset.id);
                const signItem = this.signItems[initialPage][id];
                const posX =
                    Math.round(
                        normalizePosition(pageX / width, signItem.data.width) * 1000
                    ) / 1000;
                const posY =
                    Math.round(
                        normalizePosition(pageY / height, signItem.data.height) * 1000
                    ) / 1000;

                const positionContext = { posX, posY, targetPage, initialPage, page };
                this.updateSignItemPosition(signItem, positionContext);
            } else {
                return;
            }

            this.setTemplateChanged();
            this.refreshSignItems();
        }

        /**
         * Enables resizing and drag/drop for sign items
         * @param {SignItem} signItem
         */
        enableCustom(signItem) {
            super.enableCustom(signItem);
            if (signItem.data.isSignItemEditable) {
                startResize(this, signItem, this.onResizeItem.bind(this));
                this.startSignItemInteractions(signItem);
            }
        }

        openDialogAfterInitialDrop(data) {
            this.dialog.add(ConfirmationDialog, {
                title: _t('Add Initials'),
                body: _t('Do you want to add initials to all pages?'),
                confirmLabel: _t("Yes"),
                confirm: () => this.addInitialSignItem(data, true),
                cancelLabel: _t("No, add only once"),
                cancel: () => this.addInitialSignItem(data, false),
            });
        }

        /**
         * Inserts initial sign items in the page
         * @param {Object} data data of the sign item to be added
         * @param {Boolean} targetAllPages if the item should be added in all pages or only at the current one
         */
        addInitialSignItem(data, targetAllPages = false) {
            if (targetAllPages) {
                for (let page = 1; page <= this.pageCount; page++) {
                    const id = generateRandomId();
                    const signItemData = { ...data, page, id};
                    this.signItems[page][id] = {
                        data: signItemData,
                        el: this.renderSignItem(signItemData, this.getPageContainer(page)),
                    };
                }
            } else {
                this.signItems[data.page][data.id] = {
                    data,
                    el: this.renderSignItem(data, this.getPageContainer(data.page)),
                };
            }
            this.refreshSignItems();
            this.setTemplateChanged();
        }

        /**
         * Creates and renders the inital two sign items of the radio set.
         * @param: {Object} data: the first radio item data
         */
        async addRadioSet(data) {
            const [rs_id] = await this.orm.create('sign.item.radio.set', [{}]);
            data['radio_set_id'] = rs_id;
            const id2 = generateRandomId();
            const signItemData1 = { ...data };
            const signItemData2 = { ...data };
            signItemData2['id'] = id2;
            signItemData2['posY'] += 0.02;
            this.signItems[data.page][data.id] = {
                data: signItemData1,
                el: this.renderSignItem(signItemData1, this.getPageContainer(data.page)),
            }
            this.signItems[data.page][id2] = {
                data: signItemData2,
                el: this.renderSignItem(signItemData2, this.getPageContainer(data.page)),
            }
            this.radioSets[data['radio_set_id']] = {
                num_options: 2,
                radio_item_ids: [signItemData1.id , signItemData2.id],
            };
            this.refreshSignItems();
            this.setTemplateChanged();
        }

        setTemplateChanged() {}

        /**
         * Deletes a sign item from the template
         * @param {SignItem} signItem
         */
        deleteSignItem(signItem) {
            const { id, page } = signItem.data;
            signItem.el.parentElement?.removeChild(signItem.el);
            delete this.signItems[page][id];
            this.setTemplateChanged();
        }

        /**
         * Bulk delete of multiple sign items, saves the template only once.
         * @param {SignItem []} deletedItems 
         */
        async deleteSignItems(deletedItems) {
            deletedItems.forEach((signItem) => {
                this.deletedSignItemIds.push(signItem.data.id);
                signItem.el.parentElement.removeChild(signItem.el);
                delete this.signItems[signItem.data.page][signItem.data.id];
                if (signItem.data.type == "radio") {
                    this.radioSets[signItem.data.radio_set_id].num_options--;
                    this.radioSets[signItem.data.radio_set_id].radio_item_ids = 
                        this.radioSets[signItem.data.radio_set_id].radio_item_ids.filter((id) => id != signItem.data.id);
                }
            })
            await this.setTemplateChanged();
        }
    };
