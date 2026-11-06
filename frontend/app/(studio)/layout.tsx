/**
 * Studio layout — wraps the project dashboard.
 * The per-project sidebar is added in [projectId]/layout.tsx.
 */
export default function StudioLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <div className="min-h-screen bg-background">{children}</div>
}
