export type VideoScene = {
  id: string;
  type: "video" | "image";
  assetUrl: string;
  durationInSeconds: number;
};

export type YouTubeVideoProps = {
  title: string;
  audioNarrationUrl: string;
  scenes: VideoScene[];
};
