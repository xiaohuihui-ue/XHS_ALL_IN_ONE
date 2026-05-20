import { App, ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

type ThemeMode = "dark" | "light";

const ThemeContext = createContext<{ mode: ThemeMode; toggle: () => void }>({
  mode: "dark",
  toggle: () => {},
});

export function useThemeMode() {
  return useContext(ThemeContext);
}

const darkTokens = {
  colorPrimary: "#1668dc",
  colorBgBase: "#141414",
  colorBgContainer: "#1f1f1f",
  colorBgElevated: "#262626",
  colorBorder: "#303030",
  colorBorderSecondary: "#262626",
  borderRadius: 6,
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
};

const lightTokens = {
  colorPrimary: "#1668dc",
  colorBgBase: "#ffffff",
  colorBgContainer: "#ffffff",
  colorBgElevated: "#ffffff",
  colorBorder: "#e8e8e8",
  colorBorderSecondary: "#f0f0f0",
  borderRadius: 6,
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
};

const darkCssVariables = {
  "--color-background-primary": "#141414",
  "--color-background-secondary": "#1f1f1f",
  "--color-background-elevated": "#262626",
  "--color-border": "#303030",
  "--color-border-secondary": "#262626",
  "--color-text-primary": "rgba(255,255,255,0.88)",
  "--color-text-secondary": "rgba(255,255,255,0.65)",
  "--color-text-muted": "rgba(255,255,255,0.35)",
  "--color-accent": "#1668dc",
  "--color-accent-subtle": "rgba(22,104,220,0.18)",
  "--color-row-hover": "#1a1a2e",
};

const lightCssVariables = {
  "--color-background-primary": "#f5f5f5",
  "--color-background-secondary": "#ffffff",
  "--color-background-elevated": "#ffffff",
  "--color-border": "#e8e8e8",
  "--color-border-secondary": "#f0f0f0",
  "--color-text-primary": "rgba(0,0,0,0.88)",
  "--color-text-secondary": "rgba(0,0,0,0.65)",
  "--color-text-muted": "rgba(0,0,0,0.35)",
  "--color-accent": "#1668dc",
  "--color-accent-subtle": "rgba(22,104,220,0.12)",
  "--color-row-hover": "#f0f5ff",
};

const darkComponents = {
  Layout: { siderBg: "#141414", headerBg: "#141414", bodyBg: "#0a0a0a" },
  Menu: { darkItemBg: "#141414", darkSubMenuItemBg: "#141414", darkItemSelectedBg: "#1668dc20", darkItemSelectedColor: "#1668dc" },
  Card: { colorBgContainer: "#1a1a1a" },
  Table: { colorBgContainer: "#1a1a1a", headerBg: "#1f1f1f" },
};

const lightComponents = {
  Layout: { siderBg: "#ffffff", headerBg: "#ffffff", bodyBg: "#f5f5f5" },
  Menu: {},
  Card: {},
  Table: {},
};

type AppProvidersProps = { children: ReactNode };

export function AppProviders({ children }: AppProvidersProps) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem("theme-mode");
    return saved === "light" ? "light" : "dark";
  });

  useEffect(() => {
    localStorage.setItem("theme-mode", mode);
    const variables = mode === "dark" ? darkCssVariables : lightCssVariables;
    document.documentElement.dataset.theme = mode;
    Object.entries(variables).forEach(([name, value]) => {
      document.documentElement.style.setProperty(name, value);
    });
    document.body.style.background = variables["--color-background-primary"];
  }, [mode]);

  const toggle = () => setMode((m) => (m === "dark" ? "light" : "dark"));
  const isDark = mode === "dark";

  return (
    <ThemeContext.Provider value={{ mode, toggle }}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
          token: isDark ? darkTokens : lightTokens,
          components: isDark ? darkComponents : lightComponents,
        }}
      >
        <App>{children}</App>
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}
