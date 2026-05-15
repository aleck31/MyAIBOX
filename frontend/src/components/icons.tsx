/**
 * Centralized icon imports from lucide-react.
 *
 * Plain icons are re-exported as-is. Icons with a semantic state color
 * (on/off, success/error) are wrapped so the color stays in one place.
 */
import { ToggleLeft, ToggleRight, type LucideProps } from 'lucide-react'

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
  Brain as IconBrain,
  Wrench as IconWrench,
} from 'lucide-react'

// Toggle: green when on, muted gray when off. Override with `color` prop.
export const IconToggleOn = (props: LucideProps) => (
  <ToggleRight color="hsl(142 60% 40%)" {...props} />
)
export const IconToggleOff = (props: LucideProps) => (
  <ToggleLeft color="hsl(var(--muted-foreground))" {...props} />
)
