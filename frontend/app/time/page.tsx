import { Suspense } from "react";
import { TimeBoard } from "@/components/time-board";

export default function TimePage() {
  return (
    <Suspense>
      <TimeBoard />
    </Suspense>
  );
}
