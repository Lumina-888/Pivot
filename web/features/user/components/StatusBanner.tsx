export function StatusBanner({
  tone,
  children,
}: {
  tone: "loading" | "error" | "empty" | "refused" | "uncertain";
  children: string;
}) {
  return (
    <p className="status-banner" data-tone={tone} role="status">
      {children}
    </p>
  );
}
