// Session 52: 路由占位 (无 react-router, 用 hash-state 简单分页)
// S54+ 决定是否引入 react-router

import { useEffect, useState } from "react";

export type RouteName = "home" | "legacy";

export function useRoute(): [RouteName, (next: RouteName) => void] {
  const [route, setRoute] = useState<RouteName>(() => {
    if (typeof window === "undefined") return "home";
    const h = window.location.hash.replace(/^#\/?/, "");
    return h === "legacy" ? "legacy" : "home";
  });

  useEffect(() => {
    const onHash = () => {
      const h = window.location.hash.replace(/^#\/?/, "");
      setRoute(h === "legacy" ? "legacy" : "home");
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (next: RouteName) => {
    window.location.hash = next === "home" ? "/" : `/${next}`;
  };

  return [route, navigate];
}
