/**
 * API Client for communicating with the Sepsis Sentinel backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: number;
}

/**
 * Fetch patients from the backend API
 */
export async function fetchPatients(skip: number = 0, limit: number = 10000): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/patients?skip=${skip}&limit=${limit}&_t=${Date.now()}`, {
      cache: "no-store",
    });
    
    if (!response.ok) {
      return {
        error: `Failed to fetch patients: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error fetching patients: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

/**
 * Fetch a specific patient by ID
 */
export async function fetchPatientById(patientId: string): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}?_t=${Date.now()}`, {
      cache: "no-store",
    });
    
    if (!response.ok) {
      return {
        error: `Patient not found: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error fetching patient: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

/**
 * Load CSV data into the backend
 */
export async function loadCsvData(): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/load-data`, {
      method: "POST",
    });
    
    if (!response.ok) {
      return {
        error: `Failed to load data: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error loading data: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

/**
 * Get statistics from the backend
 */
export async function fetchStatistics(): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/statistics`, {
      cache: "no-store",
    });
    
    if (!response.ok) {
      return {
        error: `Failed to fetch statistics: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error fetching statistics: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

/**
 * Clear all patient data from the backend
 */
export async function clearData(): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/data`, {
      method: "DELETE",
    });
    
    if (!response.ok) {
      return {
        error: `Failed to clear data: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error clearing data: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

/**
 * Save vital signs reading to the backend
 */
export async function saveVitals(patientId: string, vitals: {
  heart_rate: number;
  oxygen_saturation: number;
  sbp: number;
  dbp: number;
  map: number;
  respiratory_rate: number;
  temperature: number;
}): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/vitals`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        patient_id: patientId,
        ...vitals,
      }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      return {
        error: error.detail || `Failed to save vitals: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error saving vitals: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

/**
 * Fetch vital signs history for a patient
 */
/**
 * Create a new patient record
 */
export async function createPatient(patientData: {
  Patient_ID: string
  Age: number
  Gender: number
  Unit1: number
  Unit2: number
  Name?: string
}): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/patients`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(patientData),
    });
    
    if (!response.ok) {
      const error = await response.json();
      return {
        error: error.detail || `Failed to create patient: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 201,
    };
  } catch (error) {
    return {
      error: `Error creating patient: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

export async function fetchPatientVitals(patientId: string): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/vitals/${patientId}?_t=${Date.now()}`, {
      cache: "no-store",
    });
    
    if (!response.ok) {
      return {
        error: `Failed to fetch vitals: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error fetching vitals: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

/**
 * Get LSTM prediction for sepsis risk
 */
export async function getLSTMPrediction(patientId: string): Promise<ApiResponse<any>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/lstm-prediction/${patientId}`, {
      cache: "no-store",
    });
    
    if (!response.ok) {
      return {
        error: `Failed to get LSTM prediction: ${response.statusText}`,
        status: response.status,
      };
    }
    
    const data = await response.json();
    return {
      data,
      status: 200,
    };
  } catch (error) {
    return {
      error: `Error getting LSTM prediction: ${error instanceof Error ? error.message : String(error)}`,
      status: 500,
    };
  }
}

