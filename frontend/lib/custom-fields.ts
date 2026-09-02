import type { CustomFieldDef, CustomFieldKind } from "@/lib/types";

export const FIELD_KINDS: { value: CustomFieldKind; label: string }[] = [
  { value: "text", label: "текст" },
  { value: "number", label: "число" },
  { value: "date", label: "дата" },
  { value: "select", label: "выбор" },
  { value: "check", label: "чекбокс" },
];

export const FIELD_EXAMPLES: {
  name: string;
  kind: CustomFieldKind;
  options?: string[];
  hint: string;
}[] = [
  { name: "NDA", kind: "check", hint: "чекбокс · да/нет" },
  { name: "релокация", kind: "check", hint: "чекбокс" },
  { name: "тестовое", kind: "check", hint: "чекбокс" },
  { name: "дедлайн теста", kind: "date", hint: "дата" },
  { name: "ответ до", kind: "date", hint: "дата" },
  { name: "вилка оффера", kind: "number", hint: "число, ₽" },
  { name: "приоритет", kind: "select", options: ["высокий", "средний", "низкий"], hint: "выбор" },
  { name: "реферал", kind: "text", hint: "текст · кто привёл" },
];

export function newFieldId() {
  return `f${Math.random().toString(36).slice(2, 10)}`;
}

export function isCheckOn(value: string | undefined) {
  return ["1", "true", "да", "yes", "on"].includes((value || "").trim().toLowerCase());
}
