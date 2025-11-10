// API Response Types
export interface Citation {
  article_title: string
  section: string
  url: string
  paragraph_index: number
  text_excerpt: string
  similarity_score: number
}

export interface QuestionResponse {
  question: string
  answer: string
  sources: Citation[]
  disclaimer: string | null
  model: string
  metadata: {
    tokens_used: number
    cost: number
    generation_time_ms: number
    cached: boolean
    sources_count: number
  }
}

export interface HealthResponse {
  status: string
  version: string
  timestamp: string
  services: {
    vector_db: boolean
    redis_cache: boolean
    llm_client: boolean
  }
}

export interface CacheStats {
  total_queries: number
  cache_hits: number
  cache_misses: number
  cache_errors: number
  hit_rate: number
  miss_rate: number
  total_cost_saved: number
  total_time_saved_ms: number
  avg_time_saved_per_hit_ms: number
  enabled: boolean
  config: {
    enabled: boolean
    host: string
    port: number
    db: number
    ttl_seconds: number
    key_prefix: string
    max_retries: number
    timeout: number
  }
  redis_total_commands?: number
  redis_keyspace_hits?: number
  redis_keyspace_misses?: number
}

export interface LLMStats {
  provider: string
  model: string
  total_calls: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  total_cost: number
  avg_input_tokens_per_call: number
  avg_output_tokens_per_call: number
  avg_cost_per_call: number
}

export interface RetrievalStats {
  model: string
  dimensions: number
  total_tokens_used: number
  total_cost: number
  cost_per_1k_tokens: number
  batch_size: number
}

export interface StatsResponse {
  llm: LLMStats
  cache: CacheStats
  retrieval: RetrievalStats
  total_cost: number
  total_cost_saved: number
  cost_reduction_percent: number
}

export interface QuestionRequest {
  question: string
  cancer_type?: string
  max_results?: number
}
