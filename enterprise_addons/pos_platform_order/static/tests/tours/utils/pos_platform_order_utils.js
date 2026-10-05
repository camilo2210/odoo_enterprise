// export function food
export function orderButtonClick(status) {
    return [
        {
            trigger: `.validation > span:contains("${status}")`,
            run: "click",
        },
    ];
}

export function foodReadyButtonIsDisabled() {
    return [
        {
            trigger: `.validation.set-food-ready-button:disabled`,
        },
    ];
}
