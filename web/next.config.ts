import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // コンテナイメージには .next/standalone を配る（web/Dockerfile の production ステージが
  // これを COPY する）。指定が無いと standalone が生成されず、production ビルドが落ちる。
  output: "standalone",
};

export default nextConfig;
