interface PageContainerProps {
  children: React.ReactNode;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export function PageContainer({
  children,
  title,
  description,
  actions,
}: PageContainerProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-border bg-white px-6 py-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">{title}</h1>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      <main className="flex-1 overflow-auto bg-background p-6">{children}</main>
    </div>
  );
}
