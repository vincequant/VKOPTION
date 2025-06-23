'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { SWRConfig } from 'swr'

// API 配置
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// SWR 默認配置
const swrConfig = {
  fetcher: async (url: string) => {
    const apiKey = localStorage.getItem('api_key')
    if (!apiKey) {
      throw new Error('API key not found. Please login first.')
    }

    const response = await fetch(`${API_BASE_URL}${url}`, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Network error' }))
      throw new Error(error.message || `HTTP ${response.status}`)
    }

    return response.json()
  },
  refreshInterval: 30000, // 30秒自動刷新
  revalidateOnFocus: true,
  revalidateOnReconnect: true,
  shouldRetryOnError: true,
  errorRetryCount: 3,
  errorRetryInterval: 5000,
}

// 認證上下文
interface AuthContextType {
  isAuthenticated: boolean
  apiKey: string | null
  accountNumber: string | null
  login: (apiKey: string, accountNumber: string) => void
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// 主題上下文
interface ThemeContextType {
  theme: 'light' | 'dark'
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

// 通知上下文
interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
}

interface NotificationContextType {
  notifications: Notification[]
  addNotification: (notification: Omit<Notification, 'id'>) => void
  removeNotification: (id: string) => void
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined)

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return context
}

// 認證提供者
function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [accountNumber, setAccountNumber] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 從 localStorage 恢復認證狀態
    const savedApiKey = localStorage.getItem('api_key')
    const savedAccountNumber = localStorage.getItem('account_number')
    
    if (savedApiKey && savedAccountNumber) {
      setApiKey(savedApiKey)
      setAccountNumber(savedAccountNumber)
      setIsAuthenticated(true)
    }
    
    setLoading(false)
  }, [])

  const login = (newApiKey: string, newAccountNumber: string) => {
    localStorage.setItem('api_key', newApiKey)
    localStorage.setItem('account_number', newAccountNumber)
    setApiKey(newApiKey)
    setAccountNumber(newAccountNumber)
    setIsAuthenticated(true)
  }

  const logout = () => {
    localStorage.removeItem('api_key')
    localStorage.removeItem('account_number')
    setApiKey(null)
    setAccountNumber(null)
    setIsAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{
      isAuthenticated,
      apiKey,
      accountNumber,
      login,
      logout,
      loading
    }}>
      {children}
    </AuthContext.Provider>
  )
}

// 主題提供者
function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null
    if (savedTheme) {
      setTheme(savedTheme)
    } else {
      // 檢測系統主題偏好
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      setTheme(prefersDark ? 'dark' : 'light')
    }
  }, [])

  useEffect(() => {
    localStorage.setItem('theme', theme)
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

// 通知提供者
function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([])

  const addNotification = (notification: Omit<Notification, 'id'>) => {
    const id = Math.random().toString(36).substring(2, 9)
    const newNotification = {
      ...notification,
      id,
      duration: notification.duration || 5000
    }
    
    setNotifications(prev => [...prev, newNotification])

    // 自動移除通知
    if (newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id)
      }, newNotification.duration)
    }
  }

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }

  return (
    <NotificationContext.Provider value={{
      notifications,
      addNotification,
      removeNotification
    }}>
      {children}
    </NotificationContext.Provider>
  )
}

// 通知顯示組件
function NotificationDisplay() {
  const { notifications, removeNotification } = useNotifications()

  if (notifications.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={`
            max-w-sm w-full rounded-lg shadow-lg p-4 animate-slide-up
            ${notification.type === 'success' ? 'bg-success-50 border border-success-200' : ''}
            ${notification.type === 'error' ? 'bg-danger-50 border border-danger-200' : ''}
            ${notification.type === 'warning' ? 'bg-warning-50 border border-warning-200' : ''}
            ${notification.type === 'info' ? 'bg-primary-50 border border-primary-200' : ''}
          `}
        >
          <div className="flex items-start">
            <div className="flex-1">
              <h4 className={`
                font-medium text-sm
                ${notification.type === 'success' ? 'text-success-800' : ''}
                ${notification.type === 'error' ? 'text-danger-800' : ''}
                ${notification.type === 'warning' ? 'text-warning-800' : ''}
                ${notification.type === 'info' ? 'text-primary-800' : ''}
              `}>
                {notification.title}
              </h4>
              {notification.message && (
                <p className={`
                  mt-1 text-sm
                  ${notification.type === 'success' ? 'text-success-700' : ''}
                  ${notification.type === 'error' ? 'text-danger-700' : ''}
                  ${notification.type === 'warning' ? 'text-warning-700' : ''}
                  ${notification.type === 'info' ? 'text-primary-700' : ''}
                `}>
                  {notification.message}
                </p>
              )}
            </div>
            <button
              onClick={() => removeNotification(notification.id)}
              className={`
                ml-4 flex-shrink-0 rounded-md p-1 hover:bg-opacity-20 transition-colors
                ${notification.type === 'success' ? 'text-success-600 hover:bg-success-600' : ''}
                ${notification.type === 'error' ? 'text-danger-600 hover:bg-danger-600' : ''}
                ${notification.type === 'warning' ? 'text-warning-600 hover:bg-warning-600' : ''}
                ${notification.type === 'info' ? 'text-primary-600 hover:bg-primary-600' : ''}
              `}
            >
              <span className="sr-only">關閉</span>
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// 主提供者組件
export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ThemeProvider>
        <NotificationProvider>
          <SWRConfig value={swrConfig}>
            {children}
            <NotificationDisplay />
          </SWRConfig>
        </NotificationProvider>
      </ThemeProvider>
    </AuthProvider>
  )
}