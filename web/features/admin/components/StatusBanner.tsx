export function StatusBanner({
  tone,
  children,
}: {
  tone: "loading" | "error" | "empty" | "forbidden";
  children: string;
}) {
  return (
    <p className="status-banner" data-tone={tone} role="status">
      {children}
    </p>
  );
}
