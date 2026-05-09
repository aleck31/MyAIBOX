import type { ChatAgent } from '../api/client'
import assistantAvatar from '../assets/avatars/assistant.svg'
import familyDoctorAvatar from '../assets/avatars/family_doctor.svg'
import englishTeachAvatar from '../assets/avatars/english_teach.svg'
import historianAvatar from '../assets/avatars/historian.svg'
import psychologistAvatar from '../assets/avatars/psychologist.svg'
import novelistAvatar from '../assets/avatars/novelist.svg'
import userAvatar from '../assets/avatars/user.svg'

// Map of agent id → dedicated avatar image. Any agent not listed here falls
// back to a colored circle with the agent's emoji (agent.avatar).
const AVATAR_IMAGES: Record<string, string> = {
  assistant: assistantAvatar,
  family_doctor: familyDoctorAvatar,
  english_teach: englishTeachAvatar,
  historian: historianAvatar,
  psychologist: psychologistAvatar,
  novelist: novelistAvatar,
}

interface Props {
  agent: Pick<ChatAgent, 'id' | 'name' | 'avatar'>
  size?: number
}

export default function AgentAvatar({ agent, size = 28 }: Props) {
  const src = AVATAR_IMAGES[agent.id]
  const style: React.CSSProperties = { width: size, height: size }
  if (src) {
    return (
      <div className="agent-avatar agent-avatar--img" style={style}>
        <img src={src} alt={agent.name} />
      </div>
    )
  }
  return (
    <div
      className="agent-avatar agent-avatar--emoji"
      style={{ ...style, fontSize: Math.round(size * 0.55) }}
      aria-label={agent.name}
    >
      {agent.avatar}
    </div>
  )
}

/** User avatar — generic user SVG on a neutral background. */
export function UserAvatar({ username, size = 28 }: { username: string; size?: number }) {
  return (
    <div
      className="agent-avatar agent-avatar--img"
      style={{ width: size, height: size }}
      aria-label={username}
    >
      <img src={userAvatar} alt={username} />
    </div>
  )
}
