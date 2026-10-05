import { useService } from "@web/core/utils/hooks";

/**
 * @param {() => void} close
 */
export function usePlanningPopoverFooter(close) {
    const uiService = useService("ui");
    return {
        get isMobile() {
            return uiService.isSmall;
        },
        async onFooterBtnClicked(callback) {
            await callback();
            close();
        },
    };
}
