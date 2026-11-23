import React from "react";
import { Composition } from "remotion";
import { Scene1Trilemma } from "./scenes/Scene1Trilemma";
import { Scene2UBP } from "./scenes/Scene2UBP";
import { Scene3Bridges } from "./scenes/Scene3Bridges";
import { Scene4Ablation } from "./scenes/Scene4Ablation";
import { Scene5Neon } from "./scenes/Scene5Neon";
import { Scene6StallGuard } from "./scenes/Scene6StallGuard";
import { Scene7Revocation } from "./scenes/Scene7Revocation";
import { Scene8Provenance } from "./scenes/Scene8Provenance";

// Each scene renders its full animated choreography at native 1920x1080 @ 24fps (360 frames = 15s,
// with animations scaled cleanly to 24fps), and ffmpeg seamlessly holds the final settled frame
// to match the exact voiceover duration + crossfade!
const ANIM_FRAMES = 480; // 20s @ 24fps covers every single animation trigger (up to frame 470) cleanly!
const RENDER_FPS = 24;

export const RemotionRoot: React.FC = () => {
  const scenes: [string, React.FC<{ durationInFrames: number }>][] = [
    ["Scene1", Scene1Trilemma],
    ["Scene2", Scene2UBP],
    ["Scene3", Scene3Bridges],
    ["Scene4", Scene4Ablation],
    ["Scene5", Scene5Neon],
    ["Scene6", Scene6StallGuard],
    ["Scene7", Scene7Revocation],
    ["Scene8", Scene8Provenance],
  ];
  return (
    <>
      {scenes.map(([id, Comp]) => (
        <Composition
          key={id}
          id={id}
          component={() => <Comp durationInFrames={99999} />}
          durationInFrames={ANIM_FRAMES}
          fps={RENDER_FPS}
          width={1920}
          height={1080}
        />
      ))}
    </>
  );
};
