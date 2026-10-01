.popover {
    .o_knowledge_permission_panel {
        width: 420px;
        max-width: calc(100vw - #{map-get($spacers, 4)});
        max-height: 50vh;
    }
}

.o_knowledge_permission_panel {
    .o_internal_permission,
    .o_internal_visibility,
    .o_knowledge_permission_panel_members {
        .btn {
            --btn-active-border-color: var(--border-color);
            --btn-hover-border-color: var(--border-color);
        }
    }

    .o_knowledge_permission_panel_members img {
        --Avatar-size: 2.5rem;
    }
    .o_knowledge_permission_panel_members {
        img.cursor-pointer:hover {
            filter: brightness(75%);
        }
    }
}
.o_knowledge_permission_panel_remove_member.focus {
    color: $danger;
}
