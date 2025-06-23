'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import useSWR from 'swr'
import { useAuth } from '../app/providers'

// 類型定義
interface Position {
  symbol: string
  secType: 'OPT' | 'STK' | 'FUT' | 'CASH'
  currency: 'USD' | 'HKD' | 'JPY'
  position: number
  avg_cost: number
  avgCost?: number
  market_value: number
  current_price?: number
  pnl?: number
  strike?: number
  right?: 'P' | 'C'
  expiry?: string
  expiry_formatted?: string
  days_to_expiry?: number
  underlying_price?: number
  has_market_data?: boolean
  distance_percent?: number
  actual_expiry_value?: number
  capital_required?: number
}

interface PortfolioData {
  positions: Position[]
  summary?: any
  last_update?: string
  underlying_prices?: Record<string, any>
  subscription_errors?: string[]
}

// 常量
const USD_TO_HKD = 7.8

export default function ExactReplicaIBDashboard() {
  const { accountNumber } = useAuth()
  const [currentTab, setCurrentTab] = useState<'us-options' | 'hk-options' | 'stocks'>('us-options')
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' } | null>(null)

  // 獲取數據
  const { data: portfolioData, error, isLoading, mutate } = useSWR<PortfolioData>(
    accountNumber ? `/api/portfolio/${accountNumber}` : null,
    { refreshInterval: 30000 }
  )

  // 過濾持倉
  const filteredPositions = useMemo(() => {
    if (!portfolioData?.positions) return []
    
    const positions = portfolioData.positions
    switch (currentTab) {
      case 'us-options':
        return positions.filter(p => p.secType === 'OPT' && p.currency === 'USD')
      case 'hk-options':
        return positions.filter(p => p.secType === 'OPT' && p.currency === 'HKD')
      case 'stocks':
        return positions.filter(p => p.secType === 'STK')
      default:
        return []
    }
  }, [portfolioData, currentTab])

  // 計算摘要數據
  const summaryData = useMemo(() => {
    if (!filteredPositions.length) {
      return {
        totalExpiryValue: 0,
        maxCapitalRequired: 0,
        maxReturnRate: 0,
        currentReturnRate: 0
      }
    }

    if (currentTab === 'us-options') {
      let totalExpiryValue = 0
      let actualExpiryValue = 0
      let maxCapitalRequired = 0

      filteredPositions.forEach(pos => {
        // 計算實際到期價值
        if (pos.right === 'P' && pos.position < 0) {
          const avgCost = pos.avg_cost || pos.avgCost || 0
          const strike = pos.strike || 0
          const underlyingPrice = pos.underlying_price || 0
          const positionSize = Math.abs(pos.position)
          
          if (underlyingPrice > 0) {
            if (underlyingPrice >= strike) {
              // 不會被行權
              actualExpiryValue += avgCost * positionSize * 100
            } else {
              // 會被行權
              const loss = (strike - underlyingPrice - avgCost) * positionSize * 100
              actualExpiryValue -= loss
            }
          } else {
            // 沒有底層價格，保守估計
            actualExpiryValue += avgCost * positionSize * 100
          }
          
          // 計算接貨資金
          const capital = (strike - avgCost) * positionSize * 100
          maxCapitalRequired += capital
        } else {
          actualExpiryValue += Math.abs(pos.market_value || 0)
        }
        
        totalExpiryValue += Math.abs(pos.market_value || 0)
      })

      const maxReturnRate = maxCapitalRequired > 0 ? (actualExpiryValue / maxCapitalRequired * 100) : 0
      const netLiquidation = portfolioData?.summary?.NetLiquidation || 0
      const currentReturnRate = netLiquidation > 0 ? (actualExpiryValue / (netLiquidation / USD_TO_HKD) * 100) : 0

      return {
        totalExpiryValue: actualExpiryValue,
        maxCapitalRequired,
        maxReturnRate,
        currentReturnRate
      }
    } else if (currentTab === 'hk-options') {
      const totalExpiryValue = filteredPositions.reduce((sum, p) => sum + Math.abs(p.market_value || 0), 0)
      return {
        totalExpiryValue,
        maxCapitalRequired: 0,
        maxReturnRate: 0,
        currentReturnRate: 0
      }
    } else if (currentTab === 'stocks') {
      const totalValue = filteredPositions.reduce((sum, p) => {
        const underlyingPrice = portfolioData?.underlying_prices?.[p.symbol]?.price || 0
        if (underlyingPrice > 0 && p.position) {
          return sum + (p.position * underlyingPrice)
        }
        return sum + (p.market_value || 0)
      }, 0)
      return {
        totalExpiryValue: totalValue,
        maxCapitalRequired: 0,
        maxReturnRate: 0,
        currentReturnRate: 0
      }
    }

    return {
      totalExpiryValue: 0,
      maxCapitalRequired: 0,
      maxReturnRate: 0,
      currentReturnRate: 0
    }
  }, [filteredPositions, currentTab, portfolioData])

  // 排序邏輯
  const sortedPositions = useMemo(() => {
    if (!sortConfig) return filteredPositions
    
    const sorted = [...filteredPositions].sort((a, b) => {
      const aValue = a[sortConfig.key as keyof Position]
      const bValue = b[sortConfig.key as keyof Position]
      
      if (aValue === null || aValue === undefined) return 1
      if (bValue === null || bValue === undefined) return -1
      
      if (aValue < bValue) {
        return sortConfig.direction === 'asc' ? -1 : 1
      }
      if (aValue > bValue) {
        return sortConfig.direction === 'asc' ? 1 : -1
      }
      return 0
    })
    
    return sorted
  }, [filteredPositions, sortConfig])

  // 處理排序
  const handleSort = (key: string) => {
    setSortConfig(current => {
      if (!current || current.key !== key) {
        return { key, direction: 'asc' }
      }
      if (current.direction === 'asc') {
        return { key, direction: 'desc' }
      }
      return null
    })
  }

  // 格式化數字
  const formatNumber = (num: number, decimals = 2) => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    }).format(num)
  }

  // 獲取摘要標題
  const getSummaryTitle = () => {
    switch (currentTab) {
      case 'us-options':
        return '美股期權摘要'
      case 'hk-options':
        return '港股期權摘要'
      case 'stocks':
        return '股票摘要'
      default:
        return '持倉摘要'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">載入中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-500">載入失敗: {error.message}</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 頂部導航 */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <h1 className="text-xl font-semibold">IB 倉位監控</h1>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">
                最後更新: {portfolioData?.last_update || '-'}
              </span>
              <button
                onClick={() => mutate()}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                更新持倉
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 訂閱警告 */}
        {portfolioData?.subscription_errors && portfolioData.subscription_errors.length > 0 && (
          <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-yellow-800">
              ⚠️ 有 {portfolioData.subscription_errors.length} 個持倉需要付費訂閱才能獲取實時數據
            </p>
          </div>
        )}

        {/* 標籤頁（重要：放在摘要上方） */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setCurrentTab('us-options')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                currentTab === 'us-options'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              美股期權
            </button>
            <button
              onClick={() => setCurrentTab('hk-options')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                currentTab === 'hk-options'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              港股期權
            </button>
            <button
              onClick={() => setCurrentTab('stocks')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                currentTab === 'stocks'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              股票
            </button>
          </nav>
        </div>

        {/* 持倉摘要（根據當前標籤動態顯示） */}
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center">
            <span className="mr-2">📊</span>
            {getSummaryTitle()}
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-sm text-gray-600 mb-1">到期總價值</p>
              <p className="text-3xl font-bold text-green-600">
                {currentTab === 'hk-options' ? 'HK' : ''}${formatNumber(summaryData.totalExpiryValue, 0)}
              </p>
              <p className="text-sm text-gray-500">
                (HKD {formatNumber(summaryData.totalExpiryValue * (currentTab === 'hk-options' ? 1 : USD_TO_HKD), 0)})
              </p>
            </div>
            
            {currentTab === 'us-options' && (
              <div>
                <p className="text-sm text-gray-600 mb-1">最大資金需求</p>
                <p className="text-3xl font-bold">${formatNumber(summaryData.maxCapitalRequired, 0)}</p>
                <p className="text-sm text-gray-500">
                  (HKD {formatNumber(summaryData.maxCapitalRequired * USD_TO_HKD, 0)})
                </p>
              </div>
            )}
          </div>
          
          {currentTab === 'us-options' && (
            <div className="mt-4">
              <p className="text-sm text-gray-600 mb-1">資金回報率</p>
              <p className="text-2xl font-semibold text-green-600">
                最大: {formatNumber(summaryData.maxReturnRate, 1)}% / 當前: {formatNumber(summaryData.currentReturnRate, 1)}%
              </p>
            </div>
          )}
        </div>

        {/* 持倉表格 */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h3 className="text-lg font-semibold">
              {currentTab === 'us-options' && '美股期權持倉'}
              {currentTab === 'hk-options' && '港股期權持倉'}
              {currentTab === 'stocks' && '股票持倉'}
            </h3>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {currentTab === 'us-options' && (
                    <>
                      <th onClick={() => handleSort('symbol')} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                        標的 {sortConfig?.key === 'symbol' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">類型</th>
                      <th onClick={() => handleSort('strike')} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                        行權價 {sortConfig?.key === 'strike' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th onClick={() => handleSort('underlying_price')} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                        標的現價 {sortConfig?.key === 'underlying_price' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th onClick={() => handleSort('distance_percent')} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                        距離幅度 {sortConfig?.key === 'distance_percent' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">數量</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">平均成本</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">現價</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">市值</th>
                      <th onClick={() => handleSort('days_to_expiry')} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                        到期天數 {sortConfig?.key === 'days_to_expiry' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">到期價值</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">盈虧</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">數據狀態</th>
                    </>
                  )}
                  {currentTab === 'hk-options' && (
                    <>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">標的</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">類型</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">行權價</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">數量</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">平均成本</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">市值</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">到期天數</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">到期價值</th>
                    </>
                  )}
                  {currentTab === 'stocks' && (
                    <>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">股票</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">數量</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">平均成本</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">現價</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">市值 (USD)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">市值 (HKD)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">盈虧</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">盈虧 %</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {sortedPositions.map((position, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    {currentTab === 'us-options' && (
                      <>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{position.symbol}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {position.position < 0 ? 'Short' : 'Long'} {position.right === 'P' ? 'Put' : 'Call'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${position.strike}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${formatNumber(position.underlying_price || 0, 2)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm ${
                          (position.distance_percent || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {position.distance_percent !== null && position.distance_percent !== undefined
                            ? `${position.distance_percent >= 0 ? '+' : ''}${formatNumber(position.distance_percent, 1)}%`
                            : '-'
                          }
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{position.position}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${formatNumber(position.avg_cost || position.avgCost || 0, 2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${formatNumber(position.current_price || 0, 2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${formatNumber(position.market_value || 0, 0)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {position.days_to_expiry || 0} 天
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm ${
                          (position.actual_expiry_value || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          ${formatNumber(Math.abs(position.actual_expiry_value || position.market_value || 0), 0)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm ${
                          (position.pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {position.pnl !== null && position.pnl !== undefined
                            ? `${position.pnl >= 0 ? '+' : ''}$${formatNumber(Math.abs(position.pnl), 0)}`
                            : '-'
                          }
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {position.has_market_data ? (
                            <span className="text-green-600">有數據</span>
                          ) : (
                            <span className="text-yellow-600">需訂閱</span>
                          )}
                        </td>
                      </>
                    )}
                    {currentTab === 'hk-options' && (
                      <>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{position.symbol}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {position.position < 0 ? 'Short' : 'Long'} {position.right === 'P' ? 'Put' : 'Call'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">HK${position.strike}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{position.position}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          HK${formatNumber(position.avg_cost || position.avgCost || 0, 2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          HK${formatNumber(position.market_value || 0, 0)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {position.days_to_expiry || 0} 天
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600">
                          HK${formatNumber(Math.abs(position.market_value || 0), 0)}
                        </td>
                      </>
                    )}
                    {currentTab === 'stocks' && (
                      <>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{position.symbol}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{position.position}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${formatNumber(position.avg_cost || 0, 2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {position.underlying_price || position.current_price ? 
                            `$${formatNumber(position.underlying_price || position.current_price || 0, 2)}` : 
                            '無價格數據'
                          }
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          ${formatNumber(position.market_value || 0, 0)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          HK${formatNumber((position.market_value || 0) * USD_TO_HKD, 0)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm ${
                          (position.pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {position.pnl !== null && position.pnl !== undefined
                            ? `${position.pnl >= 0 ? '+' : ''}$${formatNumber(Math.abs(position.pnl), 0)}`
                            : '-'
                          }
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm ${
                          (position.pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {position.pnl !== null && position.pnl !== undefined && position.avg_cost
                            ? `${position.pnl >= 0 ? '+' : ''}${formatNumber((position.pnl / (position.position * position.avg_cost)) * 100, 1)}%`
                            : '-'
                          }
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            
            {sortedPositions.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                沒有{currentTab === 'us-options' ? '美股期權' : currentTab === 'hk-options' ? '港股期權' : '股票'}持倉
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}