import { describe, it, expect, vi } from 'vitest'
import { apiClient, fetchApiStatus } from '@/services/api'

describe('Frontend API Client', () => {
  it('has configured default baseURL', () => {
    expect(apiClient.defaults.baseURL).toBe('http://localhost:8000')
  })

  it('fetches status response successfully', async () => {
    const mockData = {
      status: 'online',
      lm_studio_connected: true,
      lm_studio_endpoint: 'http://localhost:1234/v1',
      default_llm_model: 'local-model',
      default_embedding_model: 'text-embedding-nomic-embed-text-v1.5'
    }

    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: mockData })

    const result = await fetchApiStatus()
    expect(result.status).toBe('online')
    expect(result.lm_studio_connected).toBe(true)
    expect(result.lm_studio_endpoint).toBe('http://localhost:1234/v1')
  })
})