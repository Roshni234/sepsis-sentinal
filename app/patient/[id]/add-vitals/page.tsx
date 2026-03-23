"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, Save, Loader } from "lucide-react"
import Link from "next/link"
import type { Patient, PatientVitals, VitalReading } from "@/types/patient"
import { fetchPatientById, saveVitals } from "@/lib/api-client"



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




export default function AddVitalsPage() {
  const params = useParams()
  const router = useRouter()
  const patientId = params.id as string

  const [patient, setPatient] = useState<BackendPatient | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [vitals, setVitals] = useState({
    heartRate: "",
    oxygenSaturation: "",
    sbp: "",
    dbp: "",
    respiratoryRate: "",
    temperature: "",
  })

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
    } else if (response.data) {
      setPatient(response.data as BackendPatient)
    }
    
    setIsLoading(false)
  }

  const calculateMAP = (sbp: number, dbp: number): number => {
    // MAP = DBP + 1/3(SBP - DBP)
    return Math.round(dbp + (sbp - dbp) / 3)
  }

  const handleSave = async () => {
    console.log("[v0] Saving vitals with data:", vitals)

    // Validate all fields
    if (
      !vitals.heartRate ||
      !vitals.oxygenSaturation ||
      !vitals.sbp ||
      !vitals.dbp ||
      !vitals.respiratoryRate ||
      !vitals.temperature
    ) {
      alert("Please fill in all vital signs")
      return
    }

    setIsSaving(true)
    const sbp = Number.parseFloat(vitals.sbp)
    const dbp = Number.parseFloat(vitals.dbp)
    const map = calculateMAP(sbp, dbp)

    // Save vitals to backend API
    const response = await saveVitals(patientId, {
      heart_rate: Number.parseFloat(vitals.heartRate),
      oxygen_saturation: Number.parseFloat(vitals.oxygenSaturation),
      sbp,
      dbp,
      map,
      respiratory_rate: Number.parseFloat(vitals.respiratoryRate),
      temperature: Number.parseFloat(vitals.temperature),
    })

    if (response.error) {
      alert(`Error saving vitals: ${response.error}`)
      console.error("Error saving vitals:", response.error)
      setIsSaving(false)
      return
    }

    console.log("[v0] Vitals saved successfully to database:", response.data)

    // Also save to localStorage for local tracking
    const newReading: VitalReading = {
      timestamp: new Date().toISOString(),
      heartRate: Number.parseFloat(vitals.heartRate),
      oxygenSaturation: Number.parseFloat(vitals.oxygenSaturation),
      sbp,
      dbp,
      map,
      respiratoryRate: Number.parseFloat(vitals.respiratoryRate),
      temperature: Number.parseFloat(vitals.temperature),
    }

    const vitalsKey = `vitals-${patientId}`
    const stored = localStorage.getItem(vitalsKey)
    let patientVitals: PatientVitals

    if (stored) {
      patientVitals = JSON.parse(stored)
      patientVitals.readings.push(newReading)
    } else {
      patientVitals = {
        patientId,
        readings: [newReading],
      }
    }

    localStorage.setItem(vitalsKey, JSON.stringify(patientVitals))

    setIsSaving(false)
    // Navigate back to patient details
    router.push(`/patient/${patientId}`)

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

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href={`/patient/${patientId}`}>
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-5 w-5" />
              </Button>
            </Link>
            <div>
              <h1 className="text-xl font-semibold text-foreground">Record Vital Signs</h1>
              <p className="text-sm text-muted-foreground">{patient.Name || patient.Patient_ID}</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <Card className="max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle>Enter Vital Signs</CardTitle>
            <CardDescription>Record the current vital signs for this patient</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6">
              {/* Heart Rate */}
              <div className="grid gap-2">
                <Label htmlFor="heartRate">
                  Heart Rate <span className="text-muted-foreground">(bpm)</span>
                </Label>
                <Input
                  id="heartRate"
                  type="number"
                  placeholder="e.g., 75"
                  value={vitals.heartRate}
                  onChange={(e) => setVitals({ ...vitals, heartRate: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">Normal range: 60-100 bpm</p>
              </div>

              {/* Oxygen Saturation */}
              <div className="grid gap-2">
                <Label htmlFor="oxygenSaturation">
                  Oxygen Saturation <span className="text-muted-foreground">(SpO2 %)</span>
                </Label>
                <Input
                  id="oxygenSaturation"
                  type="number"
                  placeholder="e.g., 98"
                  value={vitals.oxygenSaturation}
                  onChange={(e) => setVitals({ ...vitals, oxygenSaturation: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">Normal range: 95-100%</p>
              </div>

              {/* Blood Pressure */}
              <div className="grid gap-2">
                <Label>Blood Pressure (mmHg)</Label>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="sbp" className="text-sm text-muted-foreground">
                      Systolic (SBP)
                    </Label>
                    <Input
                      id="sbp"
                      type="number"
                      placeholder="e.g., 120"
                      value={vitals.sbp}
                      onChange={(e) => setVitals({ ...vitals, sbp: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="dbp" className="text-sm text-muted-foreground">
                      Diastolic (DBP)
                    </Label>
                    <Input
                      id="dbp"
                      type="number"
                      placeholder="e.g., 80"
                      value={vitals.dbp}
                      onChange={(e) => setVitals({ ...vitals, dbp: e.target.value })}
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">Normal range: 90-120 / 60-80 mmHg</p>
                {vitals.sbp && vitals.dbp && (
                  <p className="text-sm font-medium">
                    MAP: {calculateMAP(Number.parseFloat(vitals.sbp), Number.parseFloat(vitals.dbp))} mmHg
                  </p>
                )}
              </div>

              {/* Respiratory Rate */}
              <div className="grid gap-2">
                <Label htmlFor="respiratoryRate">
                  Respiratory Rate <span className="text-muted-foreground">(breaths/min)</span>
                </Label>
                <Input
                  id="respiratoryRate"
                  type="number"
                  placeholder="e.g., 16"
                  value={vitals.respiratoryRate}
                  onChange={(e) => setVitals({ ...vitals, respiratoryRate: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">Normal range: 12-20 breaths/min</p>
              </div>

              {/* Temperature */}
              <div className="grid gap-2">
                <Label htmlFor="temperature">
                  Temperature <span className="text-muted-foreground">(°C)</span>
                </Label>
                <Input
                  id="temperature"
                  type="number"
                  step="0.1"
                  placeholder="e.g., 37.0"
                  value={vitals.temperature}
                  onChange={(e) => setVitals({ ...vitals, temperature: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">Normal range: 36.5-37.5°C</p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-4">
                <Link href={`/patient/${patientId}`} className="flex-1">
                  <Button variant="outline" className="w-full bg-transparent" disabled={isSaving}>
                    Cancel
                  </Button>
                </Link>
                <Button onClick={handleSave} className="flex-1 gap-2" disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader className="h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      Save Vitals
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
