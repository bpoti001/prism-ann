import React from "react";
import { Composition } from "remotion";
import { Onb1Scenario } from "./onboarding/Onb1Scenario";
import { Onb2Problems } from "./onboarding/Onb2Problems";
import { Onb3UbpBridges } from "./onboarding/Onb3UbpBridges";
import { Onb4ZorderSimd } from "./onboarding/Onb4ZorderSimd";
import { Onb5QueryFlow } from "./onboarding/Onb5QueryFlow";
import { Onb6Takeaways } from "./onboarding/Onb6Takeaways";

const ONB_ANIM_FRAMES = 310;
const ONB_FPS = 24;

export const OnbRoot: React.FC = () => {
  const scenes: [string, React.FC][] = [
    ["Onb1", Onb1Scenario],
    ["Onb2", Onb2Problems],
    ["Onb3", Onb3UbpBridges],
    ["Onb4", Onb4ZorderSimd],
    ["Onb5", Onb5QueryFlow],
    ["Onb6", Onb6Takeaways],
  ];
  return (
    <>
      {scenes.map(([id, Comp]) => (
        <Composition
          key={id}
          id={id}
          component={Comp}
          durationInFrames={ONB_ANIM_FRAMES}
          fps={ONB_FPS}
          width={1920}
          height={1080}
        />
      ))}
    </>
  );
};
