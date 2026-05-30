import { Composition, CalculateMetadataFunction } from "remotion";
import { YouTubeMainVideo } from "./components/YouTubeMainVideo";
import type { YouTubeVideoProps } from "./types";
import { calculateTotalDuration } from "./utils/duration";

const FPS = 30;

const calculateMetadata: CalculateMetadataFunction<
  YouTubeVideoProps
> = async ({ props }) => {
  const totalDurationInSeconds = calculateTotalDuration(props.scenes);

  return {
    durationInFrames: Math.ceil(totalDurationInSeconds * FPS),
    props,
  };
};

const defaultProps: YouTubeVideoProps = {
  title: "Sample Video",
  audioNarrationUrl: "",
  scenes: [
    {
      id: "scene-1",
      type: "image",
      assetUrl: "https://remotion.media/placeholder.png",
      durationInSeconds: 5,
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="YouTubeVideo"
      component={YouTubeMainVideo}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
