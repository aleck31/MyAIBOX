import type { PersonaRole } from '../types/persona'

interface RoleSelectorProps {
  roles: PersonaRole[]
  value: string
  onChange: (role: string) => void
  disabled?: boolean
}

export default function RoleSelector({ roles, value, onChange, disabled }: RoleSelectorProps) {
  return (
    <select
      className="top-bar-select"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      title="Persona role"
    >
      {roles.map((role) => (
        <option key={role.key} value={role.key}>
          {role.display_name}
        </option>
      ))}
    </select>
  )
}
