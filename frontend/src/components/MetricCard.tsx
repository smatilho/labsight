interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  color?: "green" | "red" | "amber" | "blue" | "default";
}

const colorMap = {
  green: "text-ops-green",
  red: "text-ops-red",
  amber: "text-ops-amber",
  blue: "text-ops-blue",
  default: "text-ops-text",
};

export default function MetricCard({ label, value, subtext, color = "default" }: MetricCardProps) {
  return (
    <div className="bg-ops-surface border border-ops-border rounded-lg p-4">
      <p className="text-xs uppercase tracking-wider text-ops-muted mb-1">{label}</p>
      <p className={`text-2xl font-bold font-mono ${colorMap[color]}`}>{value}</p>
      {subtext && <p className="text-xs text-ops-muted mt-1">{subtext}</p>}
    </div>
  );
}
