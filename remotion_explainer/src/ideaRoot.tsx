import React from "react";
import { Composition } from "remotion";
import { Idea1Problem } from "./idea/Idea1Problem";
import { Idea2Sota } from "./idea/Idea2Sota";
import { Idea3Theory } from "./idea/Idea3Theory";
import { Idea4System } from "./idea/Idea4System";
import { Idea5Closing } from "./idea/Idea5Closing";

// 300 frames @ 24fps = 12.5s of crisp fluid animation per scene; ffmpeg seamlessly holds the
// settled state to match each scene's exact concise voiceover duration (~15-25s).
const IDEA_ANIM_FRAMES = 310;
const IDEA_FPS = 24;

export const IdeaRoot: React.FC = () => {
  const scenes: [string, React.FC][] = [
    ["Idea1", Idea1Problem],
    ["Idea2", Idea2Sota],
    ["Idea3", Idea3Theory],
    ["Idea4", Idea4System],
    ["Idea5", Idea5Closing],
  ];
  return (
    <>
      {scenes.map(([id, Comp]) => (
        <Composition
          key={id}
          id={id}
          component={Comp}
          durationInFrames={IDEA_ANIM_FRAMES}
          fps={IDEA_FPS}
          width={1920}
          height={1080}
        />
      ))}
    </>
  );
};
