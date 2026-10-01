.o_phone_install_dialog {
    --#{$prefix}modal-header-border-width: 0;
    --#{$prefix}modal-border-width: 0;

    background-image:
        radial-gradient(var(--#{$prefix}modal-bg) 50%, transparent 200%),
        radial-gradient(var(--PhoneInstallDialogDots-bg-color, rgba(0, 0, 0, 0.3)) 1px, transparent 1px);
    background-size: 100% 100%, 12px 12px;

    .o_phone_install_dialog_promo {
        --#{$prefix}gap: #{map-get($spacers, 3)};
    }

    .o_phone_install_dialog_list {
        li::marker {
            content: "check\00a0\00a0";
            font-family: var(--icon-font-family, #{$ms-font-family});
            color: $success;
        }
    }
}

