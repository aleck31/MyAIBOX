/**
 * Centralized icon imports from lucide-react.
 *
 * All functional buttons in the app (trash, refresh, close, etc.) should
 * pull from this file so the set stays curated and consistent. Agent and
 * persona avatars keep their emoji identity — those aren't icons, they're
 * characters.
 *
 * Default sizing: 14px stroke-1.5. Override with `size={...}` or
 * `className="..."` as needed.
 */
export {
  Trash2 as IconTrash,
  RefreshCw as IconRefresh,
  X as IconClose,
  Cloud as IconCloud,
  CloudUpload as IconUpload,
  FolderOpen as IconFolder,
  Check as IconCheck,
  Loader2 as IconLoading,
  Pencil as IconEdit,
  Clipboard as IconClipboard,
  Wand2 as IconWand,
  Eraser as IconEraser,
  Plus as IconPlus,
  Paperclip as IconPaperclip,
  Sparkles as IconSparkles,
  Camera as IconCamera,
} from 'lucide-react'
