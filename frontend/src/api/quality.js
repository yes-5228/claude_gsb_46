import http, { toParams } from './client.js'

export const flagMeasurement = (id, payload) => http.post(`/measurements/${id}/flag`, payload)
export const clearMeasurementFlag = (id, payload) =>
  http.post(`/measurements/${id}/clear-flag`, payload)
export const getMeasurementFlags = (id) => http.get(`/measurements/${id}/flags`)
export const listFlagLogs = (params) =>
  http.get('/measurements/flag-logs', { params: toParams(params) })
