"use client";

import { useState } from "react";
import type { CustomFieldDef, CustomFieldKind } from "@/lib/types";
import { FIELD_EXAMPLES, FIELD_KINDS, isCheckOn, newFieldId } from "@/lib/custom-fields";

function valueOf(values: Record<string, string>, id: string) {
  return values[id] ?? "";
}

export function CustomFieldInputs({
  fields,
  values,
  onChange,
  onAdd,
  onRemoveCard,
}: {
  fields: CustomFieldDef[];
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
  onAdd: (field: CustomFieldDef, scope: "card" | "hunt") => void;
  onRemoveCard?: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<CustomFieldKind>("check");
  const [options, setOptions] = useState("");
  const [scope, setScope] = useState<"card" | "hunt">("card");
  const [error, setError] = useState<string | null>(null);

  function setValue(id: string, next: string) {
    const copy = { ...values };
    if (next.trim()) copy[id] = next;
    else delete copy[id];
    onChange(copy);
  }

  function applyExample(example: (typeof FIELD_EXAMPLES)[number]) {
    setName(example.name);
    setKind(example.kind);
    setOptions((example.options || []).join(", "));
    setOpen(true);
    setError(null);
  }

  function submit() {
    const label = name.trim();
    if (!label) {
      setError("Напиши имя поля");
      return;
    }
    const opts = options
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (kind === "select" && opts.length < 2) {
      setError("Для выбора — хотя бы два варианта через запятую");
      return;
    }
    onAdd(
      { id: newFieldId(), name: label, kind, options: kind === "select" ? opts : [], scope },
      scope,
    );
    setName("");
    setOptions("");
    setKind("check");
    setOpen(false);
    setError(null);
  }

  return (
    <section className="space-y-4">
      <h3 className="text-[12px] text-muted">поля</h3>
      {fields.map((field) => {
        const value = valueOf(values, field.id);
        if (field.kind === "check") {
          const on = isCheckOn(value);
          return (
            <label key={field.id} className="flex items-center gap-2.5 text-[14px]">
              <input type="checkbox" checked={on} onChange={(e) => setValue(field.id, e.target.checked ? "1" : "0")} />
              <span>{field.name}</span>
              {field.scope === "card" && onRemoveCard ? (
                <button
                  type="button"
                  className="ml-auto text-[12px] text-muted hover:text-white"
                  onClick={() => onRemoveCard(field.id)}
                >
                  убрать
                </button>
              ) : null}
            </label>
          );
        }
        if (field.kind === "select") {
          return (
            <label key={field.id} className="block">
              <span className="mb-1.5 flex items-center justify-between gap-2 text-[12px] text-muted">
                {field.name}
                {field.scope === "card" && onRemoveCard ? (
                  <button type="button" className="text-muted hover:text-white" onClick={() => onRemoveCard(field.id)}>
                    убрать
                  </button>
                ) : null}
              </span>
              <select value={value} onChange={(e) => setValue(field.id, e.target.value)}>
                <option value="">—</option>
                {(field.options || []).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          );
        }
        const type = field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text";
        return (
          <label key={field.id} className="block">
            <span className="mb-1.5 flex items-center justify-between gap-2 text-[12px] text-muted">
              {field.name}
              {field.scope === "card" && onRemoveCard ? (
                <button type="button" className="text-muted hover:text-white" onClick={() => onRemoveCard(field.id)}>
                  убрать
                </button>
              ) : null}
            </span>
            <input
              type={type}
              value={value}
              onChange={(e) => setValue(field.id, e.target.value)}
              placeholder={field.kind === "text" ? field.name : undefined}
            />
          </label>
        );
      })}

      {!open ? (
        <button type="button" className="text-[13px] text-accent" onClick={() => setOpen(true)}>
          добавить поле
        </button>
      ) : (
        <div className="space-y-3 border-t border-white/[0.06] pt-4">
          <p className="text-[12px] text-muted">Готовые поля: нажми — имя и тип подставятся</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {FIELD_EXAMPLES.map((example) => (
              <button
                key={example.name}
                type="button"
                title={example.hint}
                className="text-[13px] text-muted hover:text-white"
                onClick={() => applyExample(example)}
              >
                {example.name}
              </button>
            ))}
          </div>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="имя поля, например NDA" />
          <div className="flex flex-wrap gap-3 text-[13px]">
            {FIELD_KINDS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`border-b pb-0.5 ${
                  kind === item.value ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
                }`}
                onClick={() => setKind(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
          {kind === "select" && (
            <input
              value={options}
              onChange={(e) => setOptions(e.target.value)}
              placeholder="варианты через запятую: высокий, средний, низкий"
            />
          )}
          <div className="flex flex-wrap gap-4 text-[13px]">
            <button
              type="button"
              className={`border-b pb-0.5 ${
                scope === "card" ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
              }`}
              onClick={() => setScope("card")}
            >
              только эта карточка
            </button>
            <button
              type="button"
              className={`border-b pb-0.5 ${
                scope === "hunt" ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
              }`}
              onClick={() => setScope("hunt")}
            >
              вся охота
            </button>
          </div>
          {error && <p className="text-[13px] text-rose-200">{error}</p>}
          <div className="flex gap-4">
            <button type="button" className="text-[13px] text-accent" onClick={submit}>
              Добавить
            </button>
            <button
              type="button"
              className="text-[13px] text-muted"
              onClick={() => {
                setOpen(false);
                setError(null);
              }}
            >
              отмена
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
