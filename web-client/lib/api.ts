import type {
  QuestionRequest,
  QuestionResponse,
  HealthResponse,
  StatsResponse,
  VectorDBStats,
} from "./types"

// Same-origin: the Vercel route table sends /api/* to the Python service.
const API_BASE_URL = ""

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
    const response = await fetch(`${API_BASE_URL}/api/health`)
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

  // Note: POST /api/v1/cache/clear and POST /api/v1/stats/reset are
  // intentionally not wrapped here. They are admin-only endpoints gated by
  // require_admin_api_key on the backend; the Admin tab that called them was
  // removed because the browser has no way to hold that secret. They remain
  // reachable directly via curl with the X-API-Key header.

  // Get vector database statistics
  async getVectorDBStats(): Promise<VectorDBStats> {
    const response = await fetch(`${API_BASE_URL}/api/v1/vector-db/stats`)
    return handleResponse<VectorDBStats>(response)
  },
}

export { ApiError }
