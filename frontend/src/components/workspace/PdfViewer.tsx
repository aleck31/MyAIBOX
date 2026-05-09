interface Props {
  url: string
  name: string
}

export default function PdfViewer({ url, name }: Props) {
  // Browser-native PDF viewer via <iframe> — matches VisionProcessor's approach.
  // Supports Range requests out of the box (backend uses FileResponse).
  return <iframe src={url} title={name} className="workspace-pdf" />
}
