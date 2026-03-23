"use client"

import { useState, useEffect } from "react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Activity, Plus, User, Loader, Bell, Moon, Sun } from "lucide-react"
import Link from "next/link"
import { fetchPatients, loadCsvData, createPatient } from "@/lib/api-client"

type Patient = {
  id: number
  Patient_ID: string
  name?: string
  Age?: number
  Gender?: number
  Unit1?: number
  Unit2?: number
  HR?: number
  O2Sat?: number
  Temp?: number
  SBP?: number
  DBP?: number
  MAP?: number
  Resp?: number
  RiskScore?: number
  Hour?: number
}


export default function DashboardPage() {
  const router = useRouter()
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  const [patients, setPatients] = useState<Patient[]>([])
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isLoadingData, setIsLoadingData] = useState(false)
  const [notifications, setNotifications] = useState<any[]>([])
  const [searchPatientId, setSearchPatientId] = useState("")
  const [newPatient, setNewPatient] = useState({
    name: "",
    age: "",
    gender: "",
    patientId: "",
    unit: "",
  })

  // Prevent hydration mismatch for theme
  useEffect(() => {
    setMounted(true)
  }, [])

  // Load patients from backend API on mount
  useEffect(() => {
    loadPatients()
  }, [])

  // Poll notifications every 30 seconds
  useEffect(() => {
    const pollNotifications = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
        const response = await fetch(`${apiUrl}/api/notifications?limit=100`, {
          cache: 'no-store'
        })
        
        if (response.ok) {
          const data = await response.json()
          const newNotifications = data.notifications || []
          
          // Filter for notifications with "missing" status or update reminders
          const recentMissing = newNotifications.filter((n: any) => 
            n.status_flag === "missing" && 
            n.message.includes("You need to update")
          )
          
          setNotifications(recentMissing)
        }
      } catch (err) {
        console.debug("Failed to fetch notifications:", err)
      }
    }

    // Poll immediately on mount
    pollNotifications()
    
    // Then poll every 30 seconds
    const interval = setInterval(pollNotifications, 30000)
    
    return () => clearInterval(interval)
  }, [])

// ✅ ADD THIS BELOW (do NOT replace the above)
useEffect(() => {
  const handleFocus = () => {
    loadPatients()
  }

  window.addEventListener("focus", handleFocus)

  return () => {
    window.removeEventListener("focus", handleFocus)
  }
}, [])

  const loadPatients = async () => {
    setIsLoading(true)
    setError(null)
    const response = await fetchPatients()
    
    if (response.error) {
      setError(response.error)
      console.error("Error loading patients:", response.error)
      setIsLoading(false)
      return
    } 
    
    if (response.data) {
      const patientsList = response.data.patients || []
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
      
      if (patientsList.length === 0) {
        setPatients([])
        setIsLoading(false)
        return
      }
      
      // Fetch most recent vitals for each patient (includes risk score)
      const patientsWithUpdates = await Promise.all(
        patientsList.map(async (patient: Patient) => {
          let updatedPatient = { ...patient }
          
          try {
            // Fetch most recent vitals
            const vitalsResponse = await fetch(
              `${apiUrl}/api/vitals/${patient.Patient_ID}?_t=${Date.now()}`,
              { 
                signal: AbortSignal.timeout(5000),
                cache: 'no-store'
              }
            )
            if (vitalsResponse.ok) {
              const vitalsData = await vitalsResponse.json()
              // Get the most recent vital reading (first in the descending list)
              if (vitalsData.vitals && vitalsData.vitals.length > 0) {
                const latestVital = vitalsData.vitals[0]
                updatedPatient = {
                  ...updatedPatient,
                  HR: latestVital.heart_rate,
                  O2Sat: latestVital.oxygen_saturation,
                  Temp: latestVital.temperature,
                  // Use risk score from patient_vitals table if available, otherwise keep patient table value
                  RiskScore: latestVital.sepsis_risk_score ?? patient.RiskScore,
                }
              }
            }
          } catch (err) {
            // Silently continue - patient may not have vitals yet, will use patient table data
            console.debug(`No vitals found for patient ${patient.Patient_ID}`)
          }
          
          return updatedPatient
        })
      )
      
      setPatients(patientsWithUpdates)
    }
    
    setIsLoading(false)
  }

  const handleLoadCsvData = async () => {
    setIsLoadingData(true)
    setError(null)
    const response = await loadCsvData()
    
    if (response.error) {
      setError(response.error)
      alert(`Error: ${response.error}`)
    } else {
      const message = String(response.data?.message || "").toLowerCase()

      if (message === "already loaded") {
        alert("already loaded")
      } else {
        alert(`Success! Loaded ${response.data?.records_loaded || 0} patient records`)
        // Reload patients after loading data
        await loadPatients()
      }
    }
    
    setIsLoadingData(false)
  }

  const handleAddPatient = async () => {
  if (
    !newPatient.name ||
    !newPatient.age ||
    !newPatient.gender ||
    !newPatient.patientId ||
    !newPatient.unit
  ) {
    alert("Please fill in all fields")
    return
  }

  // ✅ ONLY BASIC INFO — NO VITALS
  const patientData = {
    Patient_ID: newPatient.patientId,
    Age: Number(newPatient.age),
    Gender: newPatient.gender === "Male" ? 0 : newPatient.gender === "Female" ? 1 : 2,
    Unit1: newPatient.unit === "Unit 1" ? 1 : 0,
    Unit2: newPatient.unit === "Unit 2" ? 1 : 0,
    Name: newPatient.name,
  }

  const response: any = await createPatient(patientData)
  console.log("Create patient response:", response)

  if (response.error) {
    console.error("Error adding patient:", response.error)

    let message = "Failed to add patient"

    const err = response.error as any

    if (Array.isArray(err)) {
      message = err.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(", ")
    } else if (typeof err === "object") {
      message = err.message || JSON.stringify(err)
    } else {
      message = String(err)
    }

    alert("Error: " + message)
  } else {
    const patientId = newPatient.patientId

    setIsAddDialogOpen(false)

    setNewPatient({
      name: "",
      age: "",
      gender: "",
      patientId: "",
      unit: "",
    })

    // ✅ Go to add vitals page directly
    // Refresh dashboard list so the new patient appears
    try {
      await loadPatients()
    } catch (e) {
      console.debug("Failed to refresh patients after creation", e)
    }
    router.push(`/patient/${patientId}/add-vitals`)
  }
}
 
  const getRiskBadgeClasses = (score?: number) => {
  if (score === undefined || score === null) return "bg-gray-100 text-gray-600"

  if (score > 0.7) {
    return "bg-red-100 text-red-700 border border-red-200"
  }
  if (score > 0.4) {
    return "bg-yellow-100 text-yellow-700 border border-yellow-200"
  }
  return "bg-green-100 text-green-700 border border-green-200"
}

  const filteredPatients = patients.filter((patient) =>
    patient.Patient_ID.toString().toLowerCase().includes(searchPatientId.trim().toLowerCase())
  )


  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
                <Activity className="h-6 w-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-foreground">Sepsis Sentinel</h1>
                <p className="text-sm text-muted-foreground">Patient Monitoring System</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {/* Notification Bell */}
              <Link href="/notifications">
                <div className="relative cursor-pointer">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-full border-2 ${
                    notifications.length > 0 
                      ? 'border-red-500 bg-red-50 animate-fast-pulse' 
                      : 'border-gray-300 bg-gray-50'
                  }`}>
                    <Bell className={`h-5 w-5 ${
                      notifications.length > 0 ? 'text-red-600' : 'text-gray-600'
                    }`} />
                  </div>
                  {notifications.length > 0 && (
                    <div className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-red-600 flex items-center justify-center">
                      <span className="text-xs text-white font-bold">{notifications.length}</span>
                    </div>
                  )}
                </div>
              </Link>
              
              <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
              <DialogTrigger asChild>
                <Button className="gap-2">
                  <Plus className="h-4 w-4" />
                  Add New Patient
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>Add New Patient</DialogTitle>
                  <DialogDescription>Enter patient details to add them to the monitoring system</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="patientId">Patient ID</Label>
                    <Input
                      id="patientId"
                      placeholder="e.g., PT-001"
                      value={newPatient.patientId}
                      onChange={(e) => setNewPatient({ ...newPatient, patientId: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="name">Full Name</Label>
                    <Input
                      id="name"
                      placeholder="e.g., John Smith"
                      value={newPatient.name}
                      onChange={(e) => setNewPatient({ ...newPatient, name: e.target.value })}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="age">Age</Label>
                      <Input
                        id="age"
                        type="number"
                        placeholder="e.g., 45"
                        value={newPatient.age}
                        onChange={(e) => setNewPatient({ ...newPatient, age: e.target.value })}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="gender">Gender</Label>
                      <Select
                        value={newPatient.gender}
                        onValueChange={(value) => setNewPatient({ ...newPatient, gender: value })}
                      >
                        <SelectTrigger id="gender">
                          <SelectValue placeholder="Select" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Male">Male</SelectItem>
                          <SelectItem value="Female">Female</SelectItem>
                          <SelectItem value="Other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="unit">Unit</Label>
                    <Select
                      value={newPatient.unit}
                      onValueChange={(value) => setNewPatient({ ...newPatient, unit: value })}
                    >
                      <SelectTrigger id="unit">
                        <SelectValue placeholder="Select unit" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Unit 1">Unit 1</SelectItem>
                        <SelectItem value="Unit 2">Unit 2</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleAddPatient}>Add Patient</Button>
                </div>
              </DialogContent>
            </Dialog>

            {/* Theme Toggle - Rightmost */}
            {mounted && (
              <Button
                variant="outline"
                size="icon"
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                className="ml-auto"
              >
                {theme === "dark" ? (
                  <Sun className="h-4 w-4" />
                ) : (
                  <Moon className="h-4 w-4" />
                )}
              </Button>
            )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8 space-y-6">
        {/* Load Data Button */}
        <Card>
          <CardHeader>
            <CardTitle>Import Patient Data</CardTitle>
            <CardDescription>Load patient data from the CSV file into the system</CardDescription>
          </CardHeader>
          <CardContent>
            <Button 
              onClick={handleLoadCsvData}
              disabled={isLoadingData}
              className="gap-2"
            >
              {isLoadingData ? (
                <>
                  <Loader className="h-4 w-4 animate-spin" />
                  Loading Data...
                </>
              ) : (
                "Load"
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Error Display */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <p className="text-sm text-red-800">{error}</p>
            </CardContent>
          </Card>
        )}
        

        {/* Patient List */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Patient List</CardTitle>
              
            </div>
            <div className="flex items-center gap-3">
              <Input
                placeholder="Search Patient ID"
                value={searchPatientId}
                onChange={(e) => setSearchPatientId(e.target.value)}
                className="w-[220px]"
              />
              {isLoading && <Loader className="h-4 w-4 animate-spin" />}
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : patients.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <User className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No patients available</h3>
                <p className="text-muted-foreground mb-4">Click "Load" above to import patient records</p>
              </div>
            ) : filteredPatients.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-center text-muted-foreground">
                <h3 className="text-lg font-semibold text-foreground mb-2">No matching patients</h3>
                <p>Try a different Patient ID.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient ID</TableHead>
                    <TableHead>Age</TableHead>
                    <TableHead>Gender</TableHead> 
                    <TableHead>HR</TableHead>
                    <TableHead>O2Sat</TableHead>
                    <TableHead>Temp</TableHead>
                    <TableHead>Risk Score</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPatients.map((patient) => (
                    <TableRow key={patient.Patient_ID} className="cursor-pointer hover:bg-muted/50">
                      <TableCell className="font-medium">{parseInt(patient.Patient_ID) || patient.Patient_ID}</TableCell>
                      <TableCell>{patient.Age || "N/A"}</TableCell>
                      <TableCell>{patient.Gender === 0? "Male": patient.Gender === 1 ? "Female": "N/A"}</TableCell>
                      <TableCell>{patient.HR ? patient.HR.toFixed(1) : "N/A"}</TableCell>
                      <TableCell>{patient.O2Sat ? patient.O2Sat.toFixed(1) : "N/A"}</TableCell>
                      <TableCell>{patient.Temp ? patient.Temp.toFixed(1) : "N/A"}</TableCell>
                      <TableCell>
                       <Badge className={getRiskBadgeClasses(patient.RiskScore)}>
                        {patient.RiskScore !== undefined && patient.RiskScore !== null? patient.RiskScore.toFixed(2): "N/A"}
                       </Badge>

                      </TableCell>
                      <TableCell className="text-right">
                        <Link href={`/patient/${patient.Patient_ID}`}>
                          <Button size="sm" variant="default">
                            View Details
                          </Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
