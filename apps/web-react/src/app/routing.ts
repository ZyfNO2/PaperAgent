// Session 54: hash 路由, 最小实现 — ponytail 拒绝引 react-router
// 路由: #/, #/?mode=interview, #/protocols
import { useEffect, useState } from "react";

export type RouteName = "home" | "interview" | "protocols";

export interface Route {
  name: RouteName;
  params: URLSearchParams;
}

function parseRoute(): Route {
  const hash = window.location.hash || "#/";
  const [pathPart, queryPart] = hash.split("?");
  const params = new URLSearchParams(queryPart ?? "");
  const name =
    pathPart === "#/interview" || params.get("mode") === "interview"
      ? "interview"
      : pathPart === "#/protocols"
        ? "protocols"
        : "home";
  return { name, params };
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute());
  useEffect(() => {
    const handler = () => setRoute(parseRoute());
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  return route;
}

export function navigate(path: string) {
  window.location.hash = path;
}
