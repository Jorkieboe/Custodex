import axios from 'axios'

export interface ApiStatus {
  status: string
  lm_studio_connected: boolean
  lm_studio_endpoint: string
  default_llm_model: string
  default_embedding_model: string
}

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 5000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export async function fetchApiStatus(): Promise<ApiStatus> {
  const response = await apiClient.get<ApiStatus>('/api/status')
  return response.data
}