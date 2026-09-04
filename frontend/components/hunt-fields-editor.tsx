"use client";

import type { CustomFieldDef } from "@/lib/types";
import { FIELD_EXAMPLES, FIELD_KINDS, newFieldId } from "@/lib/custom-fields";
import { GuideHint } from "@/components/guide";

export function HuntFieldsEditor({
  fields,
  onChange,
  onSave,
  huntName: _huntName,
  hunts,
  huntId,
  onHuntId,
}: {
  fields: CustomFieldDef[];
  onChange: (next: CustomFieldDef[]) => void;
  onSave: () => void;
  huntName?: string;
  hunts?: { id: number; name: string }[];
  huntId?: number | null;
  onHuntId?: (id: number) => void;
}) {
  function patch(index: number, part: Partial<CustomFieldDef>) {
    onChange(fields.map((field, i) => (i === index ? { ...field, ...part } : field)));
  }

  function add(example?: (typeof FIELD_EXAMPLES)[number]) {
    if (fields.length >= 8) return;
    onChange([
      ...fields,
      {
        id: newFieldId(),
        name: example?.name ?? "",
        kind: example?.kind ?? "check",
        options: example?.options ?? [],
      },
    ]);
  }

  return (
    <div className="mx-auto w-full max-w-[480px] space-y-8 pt-4">
      <section className="space-y-2">
        <div className="flex items-center gap-1.5">
          <h2 className="text-[26px] font-semibold tracking-tight">Поля охоты</h2>
          <GuideHint id="settings.fields" />
        </div>
        <p className="text-[13px] leading-5 text-muted">До восьми полей на карточках охоты.</p>
      </section>
      {hunts && hunts.length > 1 && onHuntId && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {hunts.map((hunt) => (
            <button
              key={hunt.id}
              type="button"
              className={`border-b pb-0.5 text-[13px] ${
                hunt.id === huntId ? "border-accent text-white" : "border-transparent text-muted hover:text-white/80"
              }`}
              onClick={() => onHuntId(hunt.id)}
            >
              {hunt.name}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {FIELD_EXAMPLES.map((example) => (
          <button
            key={example.name}
            type="button"
            title={example.hint}
            className="text-[13px] text-muted hover:text-white"
            onClick={() => add(example)}
          >
            {example.name}
          </button>
        ))}
      </div>
      {fields.map((field, index) => (
        <section key={field.id} className="space-y-3 border-t border-white/[0.06] pt-6">
          <div className="flex items-center gap-3">
            <input
              value={field.name}
              onChange={(e) => patch(index, { name: e.target.value })}
              placeholder="имя поля"
              className="flex-1"
            />
            <button
              type="button"
              className="text-[13px] text-muted hover:text-rose-200"
              onClick={() => onChange(fields.filter((_, i) => i !== index))}
            >
              убрать
            </button>
          </div>
          <div className="flex flex-wrap gap-3 text-[13px]">
            {FIELD_KINDS.map((kind) => (
              <button
                key={kind.value}
                type="button"
                className={`border-b pb-0.5 ${
                  field.kind === kind.value
                    ? "border-accent text-white"
                    : "border-transparent text-muted hover:text-white/80"
                }`}
                onClick={() => patch(index, { kind: kind.value })}
              >
                {kind.label}
              </button>
            ))}
          </div>
          {field.kind === "select" && (
            <input
              value={(field.options || []).join(", ")}
              onChange={(e) =>
                patch(index, {
                  options: e.target.value
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
              placeholder="варианты через запятую"
            />
          )}
        </section>
      ))}
      <div className="flex items-center gap-5 pt-2">
        <button
          type="button"
          disabled={fields.length >= 8}
          className="text-[14px] text-accent disabled:text-muted"
          onClick={() => add()}
        >
          {fields.length >= 8 ? "уже восемь" : "добавить поле"}
        </button>
        <button type="button" className="text-[14px] text-white" onClick={onSave}>
          Сохранить
        </button>
      </div>
    </div>
  );
}
