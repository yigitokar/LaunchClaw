const relativeFormatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

const relativeDivisions: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ["second", 60],
  ["minute", 60],
  ["hour", 24],
  ["day", 7],
  ["week", 4],
  ["month", 12],
  ["year", Number.POSITIVE_INFINITY],
];

export function formatRelativeTime(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "Pending";
  }

  let delta = Math.round((new Date(timestamp).getTime() - Date.now()) / 1000);

  for (const [unit, amount] of relativeDivisions) {
    if (Math.abs(delta) < amount) {
      return relativeFormatter.format(delta, unit);
    }
    delta = Math.round(delta / amount);
  }

  return relativeFormatter.format(delta, "year");
}

export function formatDateTime(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "Pending";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

export function truncateText(value: string | null | undefined, maxLength: number): string {
  if (!value) {
    return "";
  }

  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, Math.max(0, maxLength - 3))}...`;
}
