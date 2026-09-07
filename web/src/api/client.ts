/**
 * Minimal typed fetch wrapper over the generated OpenAPI types
 * (schema.d.ts, regenerated via `npm run gen:api` whenever the FastAPI
 * side changes - see poke_calc/api/. Pydantic and these types can never
 * drift because both come from the same source: FastAPI's own OpenAPI
 * output).
 *
 * Deliberately not using a generated-client library (openapi-fetch,
 * openapi-typescript-fetch, ...) - for the handful of endpoints this app
 * has, a plain fetch wrapper keyed off `paths` is just as type-safe and
 * has one fewer dependency's conventions to learn.
 */
import type { paths } from './schema.d.ts'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type JsonBody<T> = T extends { requestBody: { content: { 'application/json': infer B } } } ? B : never
type JsonResponse<T> = T extends { responses: { 200: { content: { 'application/json': infer R } } } } ? R : never

async function request<TResponse>(method: string, path: string, body?: unknown): Promise<TResponse> {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new ApiError(res.status, detail?.detail ?? res.statusText)
  }
  return res.json() as Promise<TResponse>
}

export const api = {
  bootstrap: () =>
    request<JsonResponse<paths['/api/bootstrap']['get']>>('GET', '/api/bootstrap'),

  calculate: (body: JsonBody<paths['/api/calculate']['post']>) =>
    request<JsonResponse<paths['/api/calculate']['post']>>('POST', '/api/calculate', body),

  calculateBatch: (body: JsonBody<paths['/api/calculate/batch']['post']>) =>
    request<JsonResponse<paths['/api/calculate/batch']['post']>>('POST', '/api/calculate/batch', body),

  speed: (body: JsonBody<paths['/api/speed']['post']>) =>
    request<JsonResponse<paths['/api/speed']['post']>>('POST', '/api/speed', body),

  getTeams: () =>
    request<JsonResponse<paths['/api/teams']['get']>>('GET', '/api/teams'),

  putPreset: (teamName: string, preset: JsonBody<paths['/api/teams/{team_name}/presets']['put']>) =>
    request<JsonResponse<paths['/api/teams/{team_name}/presets']['put']>>(
      'PUT', `/api/teams/${encodeURIComponent(teamName)}/presets`, preset,
    ),

  deletePreset: (teamName: string, index: number) =>
    request<JsonResponse<paths['/api/teams/{team_name}/presets/{index}']['delete']>>(
      'DELETE', `/api/teams/${encodeURIComponent(teamName)}/presets/${index}`,
    ),

  deleteTeam: (teamName: string) =>
    request<JsonResponse<paths['/api/teams/{team_name}']['delete']>>(
      'DELETE', `/api/teams/${encodeURIComponent(teamName)}`,
    ),
}

export type Bootstrap = JsonResponse<paths['/api/bootstrap']['get']>
export type SpeciesOut = Bootstrap['species'][number]
export type MoveOut = Bootstrap['moves'][number]
export type ItemOut = Bootstrap['items'][number]
export type AbilityOut = Bootstrap['abilities'][number]
export type NatureOut = Bootstrap['natures'][number]
export type CalculateResult = JsonResponse<paths['/api/calculate']['post']>
export type KoChanceEntry = CalculateResult['ko_chances'][number]
export type SpeedResult = JsonResponse<paths['/api/speed']['post']>
export type MoveSummaryRow = JsonResponse<paths['/api/calculate/batch']['post']>['rows'][number]
export type Preset = JsonBody<paths['/api/teams/{team_name}/presets']['put']>
export type MonBuildPayload = JsonBody<paths['/api/calculate']['post']>['attacker']
export type FieldPayload = JsonBody<paths['/api/calculate']['post']>['field']
