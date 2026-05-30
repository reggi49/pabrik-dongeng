import { AbsoluteFill, Audio, random } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { wipe } from "@remotion/transitions/wipe";
import React from "react";
import type { YouTubeVideoProps } from "../types";
import { DynamicImage } from "./dynamic/DynamicImage";
import { DynamicVideo } from "./dynamic/DynamicVideo";

export const YouTubeMainVideo: React.FC<YouTubeVideoProps> = (props) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {props.audioNarrationUrl && <Audio src={props.audioNarrationUrl} />}

      <TransitionSeries>
        {props.scenes.map((scene, index) => {
          const isLastScene = index === props.scenes.length - 1;
          const durationInFrames = Math.ceil(scene.durationInSeconds * 30);

          const transRand = random(`trans-${index}`);
          let transitionType = "cut";
          if (transRand > 0.8) transitionType = "wipe";
          else if (transRand > 0.6) transitionType = "fade";

          return (
            <React.Fragment key={scene.id}>
              <TransitionSeries.Sequence durationInFrames={durationInFrames}>
                {scene.type === "image" ? (
                  <DynamicImage src={scene.assetUrl} id={scene.id} />
                ) : (
                  <DynamicVideo
                    src={scene.assetUrl}
                    id={scene.id}
                    requiredDurationInFrames={durationInFrames}
                  />
                )}
              </TransitionSeries.Sequence>

              {!isLastScene && transitionType === "fade" && (
                <TransitionSeries.Transition
                  presentation={fade()}
                  timing={linearTiming({ durationInFrames: 15 })}
                />
              )}
              {!isLastScene && transitionType === "wipe" && (
                <TransitionSeries.Transition
                  presentation={wipe()}
                  timing={linearTiming({ durationInFrames: 15 })}
                />
              )}
            </React.Fragment>
          );
        })}
      </TransitionSeries>
    </AbsoluteFill>
  );
};
