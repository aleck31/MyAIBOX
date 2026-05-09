interface Props {
  url: string
  name: string
}

export default function ImageViewer({ url, name }: Props) {
  return (
    <div className="workspace-image">
      <img src={url} alt={name} />
    </div>
  )
}
