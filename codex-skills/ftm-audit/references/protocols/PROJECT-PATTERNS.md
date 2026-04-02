# Project Pattern Detection

Pre-audit calibration: detect framework, router, state management, and API layer so wiring checks apply the right rules. This prevents false positives from applying React patterns to a Vue project, or App Router patterns to a Pages Router project.

**Cross-reference:** ftm-debug uses this same detection to calibrate its error tracing. Run once and share results with both skills.

---

## Detection Protocol

Read `package.json` dependencies and scan key config/directory signals.

### Framework Detection

| Signal | Detection | Impact on Audit |
|---|---|---|
| **React** | `react` in deps | Dimensions 1-5 all apply |
| **Next.js** | `next` in deps | File-based routing, check App vs Pages Router |
| **Vue** | `vue` in deps | `<template>` instead of JSX, check vue-router |
| **Svelte** | `svelte` in deps | Svelte components, SvelteKit file-based routes |
| **Angular** | `@angular/core` in deps | Module-based wiring, check NgModule declarations |
| **No framework** | None of the above | Skip D2 (JSX) and D3 (Routes) |

### Router Detection

| Signal | Detection | Dimension 3 Behavior |
|---|---|---|
| `react-router-dom` | dep exists | Check explicit router config file |
| `@tanstack/react-router` | dep exists | Check router config file |
| `next` + `app/` directory | `app/layout.tsx` or `app/page.tsx` exists | File-based: `app/path/page.tsx` = `/path` |
| `next` + `pages/` directory | `pages/` exists, no `app/` | File-based: `pages/foo.tsx` = `/foo` |
| `vue-router` | dep exists | Check router config file |
| SvelteKit | `@sveltejs/kit` in deps | File-based routes in `src/routes/` |

### State Management Detection

| Signal | Detection | Dimension 4 Behavior |
|---|---|---|
| `zustand` | dep exists | Check `useStore` hooks and `create()` calls |
| `@reduxjs/toolkit` | dep exists | Check `useSelector`/`useDispatch` and slice reducers |
| `jotai` | dep exists | Check `useAtom` calls |
| `recoil` | dep exists | Check `useRecoilState`/`useRecoilValue` calls |
| `pinia` | dep exists | Check `defineStore` and `useXStore()` calls |
| None detected | — | Skip D4 or adapt to any custom store pattern found |

### API Layer Detection

| Signal | Detection | Dimension 5 Behavior |
|---|---|---|
| `@tanstack/react-query` | dep exists | Check `useQuery`/`useMutation` calls |
| `swr` | dep exists | Check `useSWR` calls |
| `@trpc/client` | dep exists | Check tRPC router procedure calls |
| `@apollo/client` | dep exists | Check `useQuery`/`useMutation` with gql tags |
| `axios` / `fetch` | explicit patterns | Check direct call sites |

### Build Tool Detection

| Signal | Detection | Impact |
|---|---|---|
| `vite.config.*` exists | File scan | Entry point: `index.html` → `src/main.tsx` |
| `next.config.*` exists | File scan | Entry managed by Next.js framework |
| `webpack.config.*` exists | File scan | Check entry field in config |

---

## Dimension Activation Matrix

Based on detected patterns, set active dimensions before running Layer 2.

| Framework | D1 (Import) | D2 (JSX) | D3 (Routes) | D4 (Store) | D5 (API) |
|---|---|---|---|---|---|
| React + react-router | Standard | Standard | Router config file | Per state lib | Per API lib |
| Next.js App Router | Check `app/` tree | Standard | File-based: `page.tsx` in dir = route | Per state lib | Check Server Actions too |
| Next.js Pages Router | Check `pages/` tree | Standard | File-based: `pages/foo.tsx` = `/foo` | Per state lib | Check `getServerSideProps`/`getStaticProps` |
| Remix | Check `app/routes/` | Standard | File-based + `remix.config` | Per state lib | Check `loader`/`action` exports |
| Vue + vue-router | Standard | `<template>` | Router config file | Pinia: `defineStore` | Per API lib |
| Svelte | Standard | Svelte components | SvelteKit: `src/routes/` | Svelte stores | Per API lib |
| No framework (Node.js) | Standard | Skip D2 | Skip D3 | Skip D4 | Standard |

---

## Output

Store detected context for use by all subsequent layers. Do not include it in the report unless something unusual was detected (e.g., conflicting signals, ambiguous router type).

```
Project detected: React 18 + Vite + react-router v6 + Zustand + TanStack Query
Dimensions active: D1 ✓  D2 ✓  D3 (router config)  D4 (Zustand)  D5 (TanStack Query)
```

If signals are ambiguous (e.g., both `app/` and `pages/` directories exist), note the ambiguity and default to the more restrictive check — verify both routing patterns.
