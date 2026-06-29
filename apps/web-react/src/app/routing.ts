// Session 54/55: hash 路由, 最小实现 — ponytail 拒绝引 react-router
// 路由:
//   #/                   → home
//   #/?mode=interview    → interview
//   #/?mode=rag-eval     → rag-eval (S55)
//   #/?mode=thesis-eval  → thesis-eval (S55)
//   #/protocols          → protocols
import { useEffect, useState } from "react";

export type RouteName =
  | "home"
  | "interview"
  | "protocols"
  | "rag-eval"
  | "thesis-eval";

export interface Route {
  name: RouteName;
  params: URLSearchParams;
}

function parseRoute(): Route {
  const hash = window.location.hash || "#/";
  const [pathPart, queryPart] = hash.split("?");
  const params = new URLSearchParams(queryPart ?? "");
  const mode = params.get("mode");
  let name: RouteName;
  if (pathPart === "#/protocols") {
    name = "protocols";
  } else if (mode === "rag-eval") {
    name = "rag-eval";
  } else if (mode === "thesis-eval") {
    name = "thesis-eval";
  } else if (mode === "interview") {
    name = "interview";
  } else {
    name = "home";
  }
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
