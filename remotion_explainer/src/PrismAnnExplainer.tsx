import React from "react";
import { Series } from "remotion";
import { TIMELINE } from "./data";
import { Scene1Trilemma } from "./scenes/Scene1Trilemma";
import { Scene2UBP } from "./scenes/Scene2UBP";
import { Scene3Bridges } from "./scenes/Scene3Bridges";
import { Scene4Ablation } from "./scenes/Scene4Ablation";
import { Scene5Neon } from "./scenes/Scene5Neon";
import { Scene6StallGuard } from "./scenes/Scene6StallGuard";
import { Scene7Revocation } from "./scenes/Scene7Revocation";
import { Scene8Provenance } from "./scenes/Scene8Provenance";

const SCENE_COMPONENTS: Record<string, React.FC<{ durationInFrames: number }>> = {
  scene1_trilemma: Scene1Trilemma,
  scene2_ubp: Scene2UBP,
  scene3_bridges: Scene3Bridges,
  scene4_ablation: Scene4Ablation,
  scene5_neon: Scene5Neon,
  scene6_stall_guard: Scene6StallGuard,
  scene7_revocation: Scene7Revocation,
  scene8_provenance: Scene8Provenance,
};

export const PrismAnnExplainer: React.FC = () => {
  return (
    <Series>
      {TIMELINE.map((s) => {
        const Comp = SCENE_COMPONENTS[s.id];
        return (
          <Series.Sequence key={s.id} durationInFrames={s.durationInFrames} name={s.label}>
            <Comp durationInFrames={s.durationInFrames} />
          </Series.Sequence>
        );
      })}
    </Series>
  );
};
