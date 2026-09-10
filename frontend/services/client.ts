import axios from 'axios'

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  }
})

export interface AppConfig {
  default_llm_model: string
  default_embedding_model: string
  lm_studio_endpoint: string
  llm_endpoint?: string
  embedding_endpoint?: string
  openai_api_key?: string
  recent_projects: string[]
}

export interface ApiStatus {
  status: string
  lm_studio_connected: boolean
  lm_studio_endpoint: string
  llm_endpoint?: string
  embedding_endpoint?: string
  has_openai_api_key?: boolean
  default_llm_model: string
  default_embedding_model: string
}

export async function fetchApiStatus(): Promise<ApiStatus> {
  const resp = await apiClient.get<ApiStatus>('/api/status')
  return resp.data
}

export async function fetchAppConfig(): Promise<AppConfig> {
  const resp = await apiClient.get<AppConfig>('/api/config')
  return resp.data
}

export async function updateAppConfig(config: AppConfig): Promise<AppConfig> {
  const resp = await apiClient.put<AppConfig>('/api/config', config)
  return resp.data
}