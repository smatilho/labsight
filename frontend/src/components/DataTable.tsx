interface DataTableProps {
  columns: string[];
  rows: Record<string, React.ReactNode>[];
  emptyMessage?: string;
}

export default function DataTable({ columns, rows, emptyMessage = "No data available" }: DataTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ops-border">
            {columns.map((col) => (
              <th key={col} className="px-3 py-2 text-left text-xs uppercase tracking-wider text-ops-muted font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-4 text-center text-ops-muted">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={i} className="border-b border-ops-border/50 hover:bg-ops-surface/50">
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2 font-mono text-xs">
                    {row[col] ?? "—"}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
