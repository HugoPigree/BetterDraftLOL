import { useEffect, useRef, useState } from "react";
import type { WorldsPhase } from "../types/worlds";

const SOUND_BASE = "/sounds/worlds";

function playOneShot(src: string, volume = 0.45) {
  const audio = new Audio(src);
  audio.volume = volume;
  void audio.play().catch(() => undefined);
}

export function useWorldsAmbience(active: boolean, phase: WorldsPhase) {
  const musicRef = useRef<HTMLAudioElement | null>(null);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    if (!active || muted) {
      if (musicRef.current) {
        musicRef.current.pause();
        musicRef.current = null;
      }
      return;
    }

    const isDrafting = phase === "drafting" || phase === "draftResult";
    const track = isDrafting
      ? `${SOUND_BASE}/music-cs-draft-pick-base-layer-01.ogg`
      : `${SOUND_BASE}/music-cs-draft-ban-base-layer-01.ogg`;

    const audio = new Audio(track);
    audio.loop = true;
    audio.volume = isDrafting ? 0.22 : 0.16;
    musicRef.current = audio;
    void audio.play().catch(() => undefined);

    return () => {
      audio.pause();
      if (musicRef.current === audio) {
        musicRef.current = null;
      }
    };
  }, [active, muted, phase]);

  return { muted, toggleMute: () => setMuted((value) => !value) };
}

export function useWorldsDraftSfx(
  enabled: boolean,
  lastMove: { action: "ban" | "pick" } | null,
  muted: boolean,
) {
  const prevRef = useRef<typeof lastMove>(null);

  useEffect(() => {
    if (!enabled || muted || !lastMove || prevRef.current === lastMove) {
      return;
    }
    prevRef.current = lastMove;
    if (lastMove.action === "ban") {
      playOneShot(`${SOUND_BASE}/sfx-cs-draft-ban-enemy-team.ogg`, 0.55);
    } else {
      playOneShot(`${SOUND_BASE}/sfx-cs-draft-notif-yourpick.ogg`, 0.5);
    }
  }, [enabled, lastMove, muted]);
}
