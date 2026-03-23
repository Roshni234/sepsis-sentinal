import type { VitalReading } from "@/types/patient"

export interface SepsisRiskDetail {
  category: string
  value: number | string
  normalRange: string
  score: number
  status: "normal" | "warning" | "critical"
}

export interface SepsisRiskAssessment {
  totalScore: number
  riskLevel: "low" | "moderate" | "high"
  details: SepsisRiskDetail[]
  recommendations: string[]
}

export function calculateSepsisRisk(reading: VitalReading): SepsisRiskAssessment {
  const details: SepsisRiskDetail[] = []
  let totalScore = 0

  // Heart Rate Assessment (Normal: 60-100 bpm)
  let hrScore = 0
  let hrStatus: "normal" | "warning" | "critical" = "normal"
  if (reading.heartRate > 100 || reading.heartRate < 60) {
    hrScore = 1
    hrStatus = "warning"
  }
  if (reading.heartRate > 120 || reading.heartRate < 50) {
    hrScore = 2
    hrStatus = "critical"
  }
  details.push({
    category: "Heart Rate",
    value: `${reading.heartRate} bpm`,
    normalRange: "60-100 bpm",
    score: hrScore,
    status: hrStatus,
  })
  totalScore += hrScore

  // Oxygen Saturation Assessment (Normal: 95-100%)
  let o2Score = 0
  let o2Status: "normal" | "warning" | "critical" = "normal"
  if (reading.oxygenSaturation < 95) {
    o2Score = 1
    o2Status = "warning"
  }
  if (reading.oxygenSaturation < 90) {
    o2Score = 3
    o2Status = "critical"
  }
  details.push({
    category: "Oxygen Saturation",
    value: `${reading.oxygenSaturation}%`,
    normalRange: "95-100%",
    score: o2Score,
    status: o2Status,
  })
  totalScore += o2Score

  // MAP Assessment (Normal: 70-100 mmHg)
  let mapScore = 0
  let mapStatus: "normal" | "warning" | "critical" = "normal"
  if (reading.map < 70) {
    mapScore = 2
    mapStatus = "warning"
  }
  if (reading.map < 65) {
    mapScore = 3
    mapStatus = "critical"
  }
  details.push({
    category: "Mean Arterial Pressure",
    value: `${reading.map} mmHg`,
    normalRange: "70-100 mmHg",
    score: mapScore,
    status: mapStatus,
  })
  totalScore += mapScore

  // Respiratory Rate Assessment (Normal: 12-20 breaths/min)
  let rrScore = 0
  let rrStatus: "normal" | "warning" | "critical" = "normal"
  if (reading.respiratoryRate > 20 || reading.respiratoryRate < 12) {
    rrScore = 1
    rrStatus = "warning"
  }
  if (reading.respiratoryRate > 24 || reading.respiratoryRate < 10) {
    rrScore = 2
    rrStatus = "critical"
  }
  details.push({
    category: "Respiratory Rate",
    value: `${reading.respiratoryRate} breaths/min`,
    normalRange: "12-20 breaths/min",
    score: rrScore,
    status: rrStatus,
  })
  totalScore += rrScore

  // Temperature Assessment (Normal: 36.5-37.5°C)
  let tempScore = 0
  let tempStatus: "normal" | "warning" | "critical" = "normal"
  if (reading.temperature > 38 || reading.temperature < 36) {
    tempScore = 1
    tempStatus = "warning"
  }
  if (reading.temperature > 39 || reading.temperature < 35) {
    tempScore = 2
    tempStatus = "critical"
  }
  details.push({
    category: "Temperature",
    value: `${reading.temperature}°C`,
    normalRange: "36.5-37.5°C",
    score: tempScore,
    status: tempStatus,
  })
  totalScore += tempScore

  // Determine risk level
  let riskLevel: "low" | "moderate" | "high" = "low"
  if (totalScore >= 6) {
    riskLevel = "high"
  } else if (totalScore >= 3) {
    riskLevel = "moderate"
  }

  // Generate recommendations
  const recommendations: string[] = []
  if (riskLevel === "high") {
    recommendations.push("Immediate medical attention required")
    recommendations.push("Consider sepsis protocol activation")
    recommendations.push("Notify physician immediately")
  } else if (riskLevel === "moderate") {
    recommendations.push("Increased monitoring frequency recommended")
    recommendations.push("Review patient history for infection signs")
    recommendations.push("Consider additional diagnostic tests")
  } else {
    recommendations.push("Continue routine monitoring")
    recommendations.push("Maintain standard care protocols")
  }

  return {
    totalScore,
    riskLevel,
    details,
    recommendations,
  }
}

export function getRiskLevelBadge(riskLevel: "low" | "moderate" | "high"): {
  label: string
  variant: "default" | "secondary" | "destructive" | "outline"
  color: string
} {
  switch (riskLevel) {
    case "low":
      return { label: "Low Risk", variant: "secondary", color: "text-green-600" }
    case "moderate":
      return { label: "Moderate Risk", variant: "outline", color: "text-yellow-600" }
    case "high":
      return { label: "High Risk", variant: "destructive", color: "text-red-600" }
  }
}
