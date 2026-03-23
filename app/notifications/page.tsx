"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Activity, Bell, ArrowLeft, AlertCircle } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

type Notification = {
  timestamp: string
  patient_id: string
  hour_timestamp: string
  status_flag: string
  data_reliability_score: number
  disclaimer: string | null
  message: string
  vitals: any
  minute_readings_count?: number
}

export default function NotificationsPage() {
  const router = useRouter()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadNotifications()
    
    // Refresh every 30 seconds
    const interval = setInterval(loadNotifications, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadNotifications = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
      const response = await fetch(`${apiUrl}/api/notifications?limit=50`, {
        cache: 'no-store'
      })
      
      if (response.ok) {
        const data = await response.json()
        setNotifications(data.notifications || [])
      }
    } catch (err) {
      console.error("Failed to fetch notifications:", err)
    } finally {
      setIsLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "missing":
        return <Badge className="bg-red-100 text-red-700 border border-red-200">Missing</Badge>
      case "delayed":
        return <Badge className="bg-yellow-100 text-yellow-700 border border-yellow-200">Delayed</Badge>
      case "normal":
        return <Badge className="bg-green-100 text-green-700 border border-green-200">Normal</Badge>
      case "estimated":
        return <Badge className="bg-blue-100 text-blue-700 border border-blue-200">Estimated</Badge>
      default:
        return <Badge className="bg-gray-100 text-gray-700">{status}</Badge>
    }
  }

  const getReliabilityColor = (score: number) => {
    if (score === 0) return "text-red-600"
    if (score < 0.5) return "text-orange-600"
    if (score < 0.8) return "text-yellow-600"
    return "text-green-600"
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button 
                variant="outline" 
                size="icon"
                onClick={() => router.back()}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100">
                <Bell className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-foreground">Notifications</h1>
                <p className="text-sm text-muted-foreground">
                  {notifications.length} notification{notifications.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-orange-600" />
              System Notifications
            </CardTitle>
            <CardDescription>
              Alerts and updates about patient vitals and hourly aggregation
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Bell className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No notifications</h3>
                <p className="text-muted-foreground">You're all caught up!</p>
              </div>
            ) : (
              <div className="space-y-3">
                {notifications.map((notification, index) => (
                  <div 
                    key={index}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      notification.status_flag === "missing" 
                        ? "border-red-200 bg-red-50 hover:bg-red-100" 
                        : notification.status_flag === "delayed"
                        ? "border-yellow-200 bg-yellow-50 hover:bg-yellow-100"
                        : "border-gray-200 bg-gray-50 hover:bg-gray-100"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          {getStatusBadge(notification.status_flag)}
                          <span className="text-sm text-muted-foreground">
                            {new Date(notification.timestamp).toLocaleString()}
                          </span>
                        </div>
                        
                        <p className="font-semibold text-foreground mb-1">
                          {notification.message}
                        </p>
                        
                        <div className="grid grid-cols-2 gap-2 text-sm mt-3">
                          <div>
                            <span className="text-muted-foreground">Patient ID:</span>
                            <span className="ml-2 font-medium">{notification.patient_id}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Hour:</span>
                            <span className="ml-2 font-medium">
                              {new Date(notification.hour_timestamp).toLocaleString()}
                            </span>
                          </div>
                          
                          {notification.minute_readings_count !== undefined && (
                            <div>
                              <span className="text-muted-foreground">Readings:</span>
                              <span className="ml-2 font-medium">{notification.minute_readings_count}</span>
                            </div>
                          )}
                        </div>
                        
                        {notification.disclaimer && (
                          <div className="mt-3 p-2 bg-white rounded border border-orange-200">
                            <p className="text-sm text-orange-800">
                              ⚠️ {notification.disclaimer}
                            </p>
                          </div>
                        )}
                      </div>
                      
                      {notification.status_flag === "missing" && (
                        <Link href={`/patient/${notification.patient_id}/add-vitals`}>
                          <Button size="sm" className="bg-red-600 hover:bg-red-700">
                            Update Now
                          </Button>
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
