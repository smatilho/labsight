interface StatusBadgeProps {
  status: string | undefined | null;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = (status ?? "unknown").toLowerCase();

  let classes: string;
  if (normalized === "up" || normalized === "success") {
    classes = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  } else if (normalized === "down" || normalized === "error") {
    classes = "bg-red-500/20 text-red-400 border-red-500/30";
  } else if (normalized === "processing") {
    classes = "bg-amber-500/20 text-amber-400 border-amber-500/30";
  } else {
    classes = "bg-slate-500/20 text-slate-400 border-slate-500/30";
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${classes}`}>
      {status}
    </span>
  );
}
