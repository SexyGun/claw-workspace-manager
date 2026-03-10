import axios from 'axios'

export type ApiError = {
  detail?: string
}

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiError>(error)) {
    return error.response?.data?.detail ?? error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return '发生未知错误'
}
