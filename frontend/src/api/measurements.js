import http, { toParams } from './client.js'

export const listMeasurements = (params) => http.get('/measurements', { params: toParams(params) })
export const previewEntries = (payload) => http.post('/measurements/preview', payload)
export const createEntries = (payload) => http.post('/measurements/entries', payload)
export const deleteMeasurement = (id) => http.delete(`/measurements/${id}`)
export const entryContext = () => http.get('/measurements/entry-context')
export const getMeasurement = (id) => http.get(`/measurements/${id}`)

export const markMeasurementQuality = (id, payload) =>
  http.patch(`/measurements/${id}/quality`, payload)
export const clearMeasurementQuality = (id, payload = {}) =>
  http.delete(`/measurements/${id}/quality`, { data: payload })
export const listQualityLogs = (params) =>
  http.get('/measurements/quality-logs', { params: toParams(params) })

export const exportMeasurementsUrl = (params) =>
  `/measurements/export?${new URLSearchParams(toParams(params)).toString()}`
