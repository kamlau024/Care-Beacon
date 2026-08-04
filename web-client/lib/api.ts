import type {
  QuestionRequest,
  QuestionResponse,
  HealthResponse,
  StatsResponse,
  VectorDBStats,
} from "./types"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: any
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }))
    throw new ApiError(
      error.detail || `HTTP ${response.status}`,
      response.status,
      error
    )
  }
  return response.json()
}

export const api = {
  // Health check
  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${API_BASE_URL}/health`)
    return handleResponse<HealthResponse>(response)
  },

  // Ask a question
  async askQuestion(request: QuestionRequest): Promise<QuestionResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    })
    return handleResponse<QuestionResponse>(response)
  },

  // Get statistics
  async getStats(): Promise<StatsResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/stats`)
    return handleResponse<StatsResponse>(response)
  },

  // Clear cache
  async clearCache(): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/cache/clear`, {
      method: "POST",
    })
    return handleResponse<{ message: string }>(response)
  },

  // Reset statistics
  async resetStats(): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/stats/reset`, {
      method: "POST",
    })
    return handleResponse<{ message: string }>(response)
  },

  // Get vector database statistics
  async getVectorDBStats(): Promise<VectorDBStats> {
    const response = await fetch(`${API_BASE_URL}/api/v1/vector-db/stats`)
    return handleResponse<VectorDBStats>(response)
  },
}

export { ApiError }
