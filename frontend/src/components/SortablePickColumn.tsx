import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { ROLES } from "../hooks/useDraftState";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { DraftPick, Team } from "../types/draft";
import { ChampionSplashSlot } from "./ChampionSplashSlot";

interface SortablePickColumnProps {
  picks: DraftPick[];
  side: Team;
  confirmed: boolean;
  onChange: (picks: DraftPick[]) => void;
  editable?: boolean;
  selectedSlotIndex?: number | null;
  onSlotEdit?: (slotIndex: number) => void;
  highlightedChampion?: string | null;
  dimUnhighlighted?: boolean;
}

function sortableId(side: Team, champion: string): string {
  return `${side}-${champion}`;
}

function SortableRoleSlot({
  pick,
  side,
  index,
  disabled,
  editable,
  selected,
  highlighted,
  dimmed,
  onEdit,
}: {
  pick: DraftPick;
  side: Team;
  index: number;
  disabled: boolean;
  editable?: boolean;
  selected?: boolean;
  highlighted?: boolean;
  dimmed?: boolean;
  onEdit?: () => void;
}) {
  const id = sortableId(side, pick.champion);
  const useDragHandle = Boolean(editable && !disabled);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
    disabled,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const dragHandleProps = useDragHandle ? { ...attributes, ...listeners } : {};
  const slotDragProps = !useDragHandle && !disabled ? { ...attributes, ...listeners } : {};

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={[
        "role-slot-sortable",
        isDragging ? "role-slot-sortable--dragging" : "",
        disabled ? "role-slot-sortable--locked" : "",
        useDragHandle ? "role-slot-sortable--with-handle" : "",
      ].join(" ")}
      {...slotDragProps}
    >
      <ChampionSplashSlot
        pick={pick}
        side={side}
        index={index}
        draggable={!useDragHandle && !disabled}
        showDragBadge={!disabled && !useDragHandle}
        editable={editable && !disabled}
        selected={selected}
        highlighted={highlighted}
        dimmed={dimmed}
        onEdit={onEdit}
      />
      {useDragHandle && (
        <button
          type="button"
          className="role-slot-sortable__handle"
          aria-label={`Glisser ${pick.champion} pour changer de rôle`}
          {...dragHandleProps}
        >
          ⠿
        </button>
      )}
    </div>
  );
}

export function SortablePickColumn({
  picks,
  side,
  confirmed,
  onChange,
  editable = false,
  selectedSlotIndex = null,
  onSlotEdit,
  highlightedChampion = null,
  dimUnhighlighted = false,
}: SortablePickColumnProps) {
  const isMobile = useMediaQuery("(max-width: 860px)");
  const [activeChampion, setActiveChampion] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const itemIds = picks.map((pick) => sortableId(side, pick.champion));
  const activePick = activeChampion ? picks.find((pick) => pick.champion === activeChampion) : null;
  const activeIndex = activePick ? picks.indexOf(activePick) : -1;
  const sortingStrategy = isMobile ? horizontalListSortingStrategy : verticalListSortingStrategy;

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
        <SortableContext items={itemIds} strategy={sortingStrategy}>
          {picks.map((pick, index) => (
            <SortableRoleSlot
              key={sortableId(side, pick.champion)}
              pick={pick}
              side={side}
              index={index}
              disabled={confirmed}
              editable={editable}
              selected={selectedSlotIndex === index}
              highlighted={Boolean(
                highlightedChampion &&
                  pick.champion.toLowerCase() === highlightedChampion.toLowerCase(),
              )}
              dimmed={Boolean(
                dimUnhighlighted &&
                  highlightedChampion &&
                  pick.champion.toLowerCase() !== highlightedChampion.toLowerCase(),
              )}
              onEdit={onSlotEdit ? () => onSlotEdit(index) : undefined}
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
