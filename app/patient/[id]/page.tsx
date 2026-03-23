"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Activity, Heart, Droplets, Gauge, Wind, Thermometer, AlertCircle, Loader } from "lucide-react"
import Link from "next/link"
import type { Patient, PatientVitals, VitalReading } from "@/types/patient"
import { calculateSepsisRisk, getRiskLevelBadge, type SepsisRiskAssessment } from "@/lib/sepsis-calculator"
import { fetchPatientById, fetchPatientVitals, getLSTMPrediction } from "@/lib/api-client"
import { formatTimeForUI } from "@/lib/datetime-utils"

interface BackendPatient {
  id: number
  Patient_ID: string
  Hour: number
  HR: number
  O2Sat: number
  Temp: number
  SBP: number
  MAP: number
  DBP: number
  Resp: number
  Age: number
  Gender: number
  Unit1: number
  Unit2: number
  RiskScore: number
  Name?: string
}

export default function PatientDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const patientId = params.id as string

  const [patient, setPatient] = useState<BackendPatient | null>(null)
  const [vitals, setVitals] = useState<VitalReading | null>(null)
  const [riskAssessment, setRiskAssessment] = useState<SepsisRiskAssessment | null>(null)
  const [lstmRiskScore, setLstmRiskScore] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadPatientData()
  }, [patientId])

  const loadPatientData = async () => {
  setIsLoading(true)
  setError(null)

  const response = await fetchPatientById(patientId)

  if (response.error) {
    setError(response.error)
    console.error("Error loading patient:", response.error)
    setIsLoading(false)
    return
  }

  if (response.data) {
    const backendPatient = response.data as BackendPatient
    setPatient(backendPatient)

    // Fetch vitals
    const vitalsResponse = await fetchPatientVitals(patientId)

    if (
      !vitalsResponse.error &&
      vitalsResponse.data &&
      vitalsResponse.data.vitals &&
      vitalsResponse.data.vitals.length > 0
    ) {
      const latestVitals = vitalsResponse.data.vitals[0]

      const reading: VitalReading = {
        timestamp: latestVitals.timestamp,
        heartRate: latestVitals.heart_rate,
        oxygenSaturation: latestVitals.oxygen_saturation,
        sbp: latestVitals.sbp,
        dbp: latestVitals.dbp,
        map: latestVitals.map,
        respiratoryRate: latestVitals.respiratory_rate,
        temperature: latestVitals.temperature,
      }

      setVitals(reading)

      const assessment = calculateSepsisRisk(reading)
      setRiskAssessment(assessment)
    } else {
      // No vitals in patient_vitals table - use initial readings from patients table
      if (backendPatient.HR && backendPatient.O2Sat && backendPatient.Temp && 
          backendPatient.SBP && backendPatient.DBP && backendPatient.MAP && backendPatient.Resp) {
        const initialReading: VitalReading = {
          timestamp: new Date().toISOString(), // Current time as placeholder
          heartRate: backendPatient.HR,
          oxygenSaturation: backendPatient.O2Sat,
          sbp: backendPatient.SBP,
          dbp: backendPatient.DBP,
          map: backendPatient.MAP,
          respiratoryRate: backendPatient.Resp,
          temperature: backendPatient.Temp,
        }

        setVitals(initialReading)

        const assessment = calculateSepsisRisk(initialReading)
        setRiskAssessment(assessment)
      } else {
        setVitals(null)
        setRiskAssessment(null)
      }
    }

    // Fetch LSTM risk score (prefer from patient_vitals, fallback to patients table)
    const lstmResponse = await getLSTMPrediction(patientId)
    if (!lstmResponse.error && lstmResponse.data) {
      setLstmRiskScore(lstmResponse.data.lstm_risk_score)
    } else if (backendPatient.RiskScore !== undefined && backendPatient.RiskScore !== null) {
      // Use initial risk score from patients table if LSTM prediction not available
      setLstmRiskScore(backendPatient.RiskScore)
    }
  }

  setIsLoading(false)
}

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Card className="w-96">
          <CardHeader>
            <CardTitle>Loading Patient Data</CardTitle>
            <CardDescription>Please wait while we fetch patient information</CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <Loader className="h-6 w-6 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !patient) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Card className="w-96">
          <CardHeader>
            <CardTitle>Error Loading Patient</CardTitle>
            <CardDescription>{error || "Patient not found"}</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/">
              <Button className="w-full">Back to Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  const riskInfo = riskAssessment ? getRiskLevelBadge(riskAssessment.riskLevel) : null

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/">
                <Button variant="ghost" size="icon">
                  <ArrowLeft className="h-5 w-5" />
                </Button>
              </Link>
              <div>
                <h1 className="text-xl font-semibold text-foreground">{patient.Name || patient.Patient_ID}</h1>
                <p className="text-sm text-muted-foreground">
                  {patient.Age} years • {patient.Gender === 0 ? "Male" : "Female"} • Unit {patient.Unit1 === 1 ? "1" : "2"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {!vitals || !riskAssessment ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Activity className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Vitals Recorded</h3>
              <p className="text-muted-foreground mb-4">Start monitoring by adding the first vital readings</p>
              <Link href={`/patient/${patientId}/add-vitals`}>
                <Button>Add Vital Signs</Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* LSTM Risk Prediction Card */}
            {lstmRiskScore !== null && (
              <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5 text-blue-600" />
                    LSTM Early Risk Detection
                  </CardTitle>
                  <CardDescription>AI-powered sepsis prediction based on patient vitals history</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-3xl font-bold text-blue-600">{(lstmRiskScore * 100).toFixed(1)}%</div>
                      <div className="text-sm text-muted-foreground mt-1">Predicted Risk Level</div>
                    </div>
                    <div className="text-right">
                      <Badge 
                        variant={lstmRiskScore > 0.7 ? "destructive" : lstmRiskScore > 0.4 ? "secondary" : "outline"}
                        className="text-base px-3 py-1"
                      >
                        {lstmRiskScore > 0.7 ? "High Risk" : lstmRiskScore > 0.4 ? "Medium Risk" : "Low Risk"}
                      </Badge>
                      <p className="text-xs text-muted-foreground mt-2">Score: {lstmRiskScore.toFixed(4)}</p>
                    </div>
                  </div>
                  <div className="h-3 bg-muted rounded-full overflow-hidden mt-4">
                    <div
                      className={`h-full transition-all ${
                        lstmRiskScore > 0.7 ? "bg-red-500" : lstmRiskScore > 0.4 ? "bg-yellow-500" : "bg-green-500"
                      }`}
                      style={{ width: `${lstmRiskScore * 100}%` }}
                    />
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Vital Signs Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {/* Heart Rate */}
              <Card className="relative overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Heart Rate</CardTitle>
                  <div className="p-2 rounded-lg bg-red-100 dark:bg-red-950">
                    <Heart className="h-5 w-5 text-red-600 dark:text-red-400" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <div className="text-3xl font-bold">{vitals.heartRate}</div>
                    <span className="text-sm text-muted-foreground font-medium">bpm</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Normal: 60-100 bpm</p>
                  {(vitals.heartRate > 100 || vitals.heartRate < 60) && (
                    <div className="mt-2 flex items-center gap-1">
                      <div
                        className={`h-2 w-2 rounded-full ${vitals.heartRate > 120 || vitals.heartRate < 50 ? "bg-red-500" : "bg-yellow-500"}`}
                      />
                      <span className="text-xs text-muted-foreground">
                        {vitals.heartRate > 120 || vitals.heartRate < 50 ? "Critical" : "Abnormal"}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Oxygen Saturation */}
              <Card className="relative overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Oxygen Saturation</CardTitle>
                  <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-950">
                    <Droplets className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <div className="text-3xl font-bold">{vitals.oxygenSaturation}</div>
                    <span className="text-sm text-muted-foreground font-medium">%</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Normal: 95-100%</p>
                  {vitals.oxygenSaturation < 95 && (
                    <div className="mt-2 flex items-center gap-1">
                      <div
                        className={`h-2 w-2 rounded-full ${vitals.oxygenSaturation < 90 ? "bg-red-500" : "bg-yellow-500"}`}
                      />
                      <span className="text-xs text-muted-foreground">
                        {vitals.oxygenSaturation < 90 ? "Critical" : "Low"}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Blood Pressure */}
              <Card className="relative overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Blood Pressure</CardTitle>
                  <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-950">
                    <Activity className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <div className="text-3xl font-bold">
                      {vitals.sbp}/{vitals.dbp}
                    </div>
                    <span className="text-sm text-muted-foreground font-medium">mmHg</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">SBP/DBP</p>
                  {(vitals.sbp > 140 || vitals.sbp < 90 || vitals.dbp > 90 || vitals.dbp < 60) && (
                    <div className="mt-2 flex items-center gap-1">
                      <div className="h-2 w-2 rounded-full bg-yellow-500" />
                      <span className="text-xs text-muted-foreground">Abnormal</span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* MAP */}
              <Card className="relative overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Mean Arterial Pressure</CardTitle>
                  <div className="p-2 rounded-lg bg-orange-100 dark:bg-orange-950">
                    <Gauge className="h-5 w-5 text-orange-600 dark:text-orange-400" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <div className="text-3xl font-bold">{vitals.map}</div>
                    <span className="text-sm text-muted-foreground font-medium">mmHg</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Normal: 70-100 mmHg</p>
                  {vitals.map < 70 && (
                    <div className="mt-2 flex items-center gap-1">
                      <div className={`h-2 w-2 rounded-full ${vitals.map < 65 ? "bg-red-500" : "bg-yellow-500"}`} />
                      <span className="text-xs text-muted-foreground">{vitals.map < 65 ? "Critical" : "Low"}</span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Respiratory Rate */}
              <Card className="relative overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Respiratory Rate</CardTitle>
                  <div className="p-2 rounded-lg bg-teal-100 dark:bg-teal-950">
                    <Wind className="h-5 w-5 text-teal-600 dark:text-teal-400" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <div className="text-3xl font-bold">{vitals.respiratoryRate}</div>
                    <span className="text-sm text-muted-foreground font-medium">/min</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Normal: 12-20 breaths/min</p>
                  {(vitals.respiratoryRate > 20 || vitals.respiratoryRate < 12) && (
                    <div className="mt-2 flex items-center gap-1">
                      <div
                        className={`h-2 w-2 rounded-full ${vitals.respiratoryRate > 24 ? "bg-red-500" : "bg-yellow-500"}`}
                      />
                      <span className="text-xs text-muted-foreground">
                        {vitals.respiratoryRate > 24 ? "Critical" : "Abnormal"}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Temperature */}
              <Card className="relative overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Temperature</CardTitle>
                  <div className="p-2 rounded-lg bg-rose-100 dark:bg-rose-950">
                    <Thermometer className="h-5 w-5 text-rose-600 dark:text-rose-400" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <div className="text-3xl font-bold">{vitals.temperature}</div>
                    <span className="text-sm text-muted-foreground font-medium">°C</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Normal: 36.5-37.5°C</p>
                  {(vitals.temperature > 38 || vitals.temperature < 36) && (
                    <div className="mt-2 flex items-center gap-1">
                      <div
                        className={`h-2 w-2 rounded-full ${vitals.temperature > 39 || vitals.temperature < 35 ? "bg-red-500" : "bg-yellow-500"}`}
                      />
                      <span className="text-xs text-muted-foreground">
                        {vitals.temperature > 39 || vitals.temperature < 35 ? "Critical" : "Abnormal"}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Last Updated */}
            <Card>
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-medium">Last Updated</p>
                  <p className="text-sm text-muted-foreground">{formatTimeForUI(vitals.timestamp)}</p>
                </div>
                <Link href={`/patient/${patientId}/add-vitals`}>
                  <Button>Update Vitals</Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  )
}
