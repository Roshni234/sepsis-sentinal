export type Patient = {
  id: string
  name: string
  age: number
  gender: string
  unit: string
  addedDate: string
}

export type VitalReading = {
  timestamp: string
  heartRate: number
  oxygenSaturation: number
  sbp: number
  dbp: number
  map: number
  respiratoryRate: number
  temperature: number
}

export type PatientVitals = {
  patientId: string
  readings: VitalReading[]
}
