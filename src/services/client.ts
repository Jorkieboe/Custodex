import axios from 'axios'

export interface ApiStatus {
  status: string
  lm_studio_connected: boolean
  lm_studio_endpoint: string
  default_llm_model: string
  default_embedding_model: string
}

export interface AppConfig {
  default_llm_model: string
  default_embedding_model: string
  lm_studio_endpoint: string
  recent_projects: string[]
}

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export async function fetchApiStatus(): Promise<ApiStatus> {
  const response = await apiClient.get<ApiStatus>('/api/status')
  return response.data
}

export async function fetchAppConfig(): Promise<AppConfig> {
  const response = await apiClient.get<AppConfig>('/api/config')
  return response.data
}

export async function updateAppConfig(config: AppConfig): Promise<AppConfig> {
  const response = await apiClient.put<AppConfig>('/api/config', config)
  return response.data
}