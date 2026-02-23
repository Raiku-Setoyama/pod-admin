import useSWR from 'swr'
import { apiClient } from '@/lib/api/client'
import type { User } from '@/types/api'

export function useCurrentUser() {
  const { data, error, isLoading, mutate } = useSWR<User>(
    '/auth/me',
    (endpoint: string) => apiClient<User>(endpoint)
  )

  return {
    user: data,
    isLoading,
    error,
    mutate,
  }
}
