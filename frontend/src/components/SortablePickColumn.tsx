import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { ROLES } from "../hooks/useDraftState";
import type { DraftPick, Team } from "../types/draft";
import { ChampionSplashSlot } from "./ChampionSplashSlot";

interface SortablePickColumnProps {
  picks: DraftPick[];
  side: Team;
  confirmed: boolean;
  onChange: (picks: DraftPick[]) => void;
}

function sortableId(side: Team, champion: string): string {
  return `${side}-${champion}`;
}

function SortableRoleSlot({
  pick,
  side,
  index,
  disabled,
}: {
  pick: DraftPick;
  side: Team;
  index: number;
  disabled: boolean;
}) {
  const id = sortableId(side, pick.champion);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
    disabled,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={[
        "role-slot-sortable",
        isDragging ? "role-slot-sortable--dragging" : "",
        disabled ? "role-slot-sortable--locked" : "",
      ].join(" ")}
      {...attributes}
      {...listeners}
    >
      <ChampionSplashSlot pick={pick} side={side} index={index} draggable showDragBadge={!disabled} />
    </div>
  );
}

export function SortablePickColumn({ picks, side, confirmed, onChange }: SortablePickColumnProps) {
  const [activeChampion, setActiveChampion] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const itemIds = picks.map((pick) => sortableId(side, pick.champion));
  const activePick = activeChampion ? picks.find((pick) => pick.champion === activeChampion) : null;
  const activeIndex = activePick ? picks.indexOf(activePick) : -1;

  function handleDragStart(event: DragStartEvent) {
    const champion = String(event.active.id).replace(`${side}-`, "");
    setActiveChampion(champion);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveChampion(null);
    const { active, over } = event;
    if (!over || active.id === over.id || confirmed) {
      return;
    }

    const oldIndex = itemIds.indexOf(String(active.id));
    const newIndex = itemIds.indexOf(String(over.id));
    if (oldIndex < 0 || newIndex < 0) {
      return;
    }

    const reordered = arrayMove(picks, oldIndex, newIndex);
    const withRoles = reordered.map((pick, index) => ({
      champion: pick.champion,
      role: ROLES[index],
    }));
    onChange(withRoles);
  }

  function handleDragCancel() {
    setActiveChampion(null);
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="drafter__picks-sortable">
        <SortableContext items={itemIds} strategy={verticalListSortingStrategy}>
          {picks.map((pick, index) => (
            <SortableRoleSlot
              key={sortableId(side, pick.champion)}
              pick={pick}
              side={side}
              index={index}
              disabled={confirmed}
            />
          ))}
        </SortableContext>
      </div>

      <DragOverlay dropAnimation={{ duration: 220, easing: "cubic-bezier(0.18, 0.67, 0.6, 1)" }}>
        {activePick && activeIndex >= 0 ? (
          <div className="role-slot-sortable role-slot-sortable--overlay">
            <ChampionSplashSlot
              pick={activePick}
              side={side}
              index={activeIndex}
              draggable
              showDragBadge
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
