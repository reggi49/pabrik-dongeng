import { config } from "@remotion/cli/config";
import { enableTailwind } from "@remotion/tailwind-v4";

config.setVideoImageFormat("jpeg");
config.setOverwriteOutput(true);
config.overrideWebpackConfig(enableTailwind);
