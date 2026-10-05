import { folderActionArchive } from "./folder_action_archive";
import { folderActionCopyLink } from "./folder_action_copy_link";
import { folderActionDeepSearch } from "./folder_action_deep_search";
import { folderActionDownload } from "./folder_action_download";
import { folderActionNewFolder } from "./folder_action_new_folder";
import { folderActionShare } from "./folder_action_share";
import { folderActionRename } from "./folder_action_rename";
import { folderActionStar, folderActionStarRemove } from "./folder_action_star";
import {
    folderActionDuplicate,
    folderActionMove,
    folderActionShortcut,
} from "./folder_action_operations";

/** @typedef {{Component: FolderAction, groupNumber: Number, isDisplayed: Function}} folderAction */

/** @type { folderAction[] } */
export const folderActions = [
    folderActionNewFolder,

    folderActionDownload,
    folderActionShare,

    folderActionRename,
    folderActionMove,
    folderActionDuplicate,
    folderActionStar,
    folderActionStarRemove,
    folderActionShortcut,
    folderActionCopyLink,
    folderActionDeepSearch,

    folderActionArchive,
];
