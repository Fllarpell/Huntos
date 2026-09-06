export function marketLabel(verdict: string | null | undefined): string {
  if (verdict === "alive") return "есть вакансии";
  if (verdict === "dead") return "почти нет";
  if (verdict === "weak") return "мало вакансий";
  return "пока рано";
}

export function marketTone(verdict: string | null | undefined): string {
  if (verdict === "alive") return "text-emerald-200";
  if (verdict === "dead") return "text-rose-200";
  return "text-amber-200";
}

export function marketDot(verdict: string | null | undefined): string {
  if (verdict === "alive") return "bg-emerald-300";
  if (verdict === "dead") return "bg-rose-300";
  return "bg-amber-300";
}
