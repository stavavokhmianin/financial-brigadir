// Динамическая часть конфигурации: http к локальному API (Wi-Fi, эмулятор) разрешён
// только в сборках для разработки и демо; production — только https.
module.exports = ({ config }) => {
  const production = process.env.EAS_BUILD_PROFILE === "production";
  return {
    ...config,
    plugins: [
      ...(config.plugins ?? []),
      ["expo-build-properties", { android: { usesCleartextTraffic: !production } }],
    ],
  };
};
