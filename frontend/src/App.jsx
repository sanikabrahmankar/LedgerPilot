import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'

const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000').replace(/\/$/, '')
const POLL_INTERVAL_MS = 5000

const formatStatus = (status) => (status || 'unknown').replace(/_/g, ' ')
const errorMessage = (error) => error?.response?.data?.error || error?.message || 'Unexpected error'

function App() {
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [online, setOnline] = useState(true)
  const [actionError, setActionError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const fileInputRef = useRef(null)

  const fetchInvoices = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/api/invoices`)
      const allInvoices = Array.isArray(response.data) ? response.data : []
      
      // Filter out invoices that have reached a terminal status
      const activeInvoices = allInvoices.filter(
        inv => !['rejected', 'rejected_by_human', 'paid_successfully'].includes(inv.status)
      )
      
      setInvoices(activeInvoices)
      setOnline(true)
    } catch (error) {
      console.error('Error fetching invoices:', error)
      setOnline(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInvoices()
    // Auto-refresh the dashboard every 5 seconds to show webhook state changes
    const interval = setInterval(fetchInvoices, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [fetchInvoices])

  const runAction = async (id, action) => {
    setBusyId(id)
    setActionError('')
    try {
      await axios.post(`${API_URL}/api/invoices/${id}/${action}`)
    } catch (error) {
      setActionError(errorMessage(error))
    } finally {
      setBusyId(null)
      fetchInvoices()
    }
  }

  const handleUpload = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setActionError('')
    try {
      const formData = new FormData()
      formData.append('invoice', file)
      await axios.post(`${API_URL}/api/upload-invoice`, formData)
    } catch (error) {
      setActionError(errorMessage(error))
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      fetchInvoices()
    }
  }

  if (loading) return <div className="p-10 text-center text-xl">Loading LedgerPilot...</div>

  return (
    <div className="min-h-screen bg-slate-50 p-8 font-sans">
      <header className="mb-10 flex flex-wrap justify-between items-end gap-4 border-b pb-4">
        <div>
          <h1 className="text-4xl font-bold text-slate-900 tracking-tight">LedgerPilot</h1>
          <p className="text-slate-500 mt-1">Autonomous Accounts Payable Agent</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={handleUpload}
            className="hidden"
            id="invoice-upload"
          />
          <label
            htmlFor="invoice-upload"
            className={`px-4 py-2 rounded font-semibold shadow-sm cursor-pointer text-white ${
              uploading ? 'bg-slate-400 pointer-events-none' : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {uploading ? 'Processing...' : 'Upload Invoice PDF'}
          </label>
          <div className="text-sm font-semibold text-slate-600 bg-white px-4 py-2 rounded shadow-sm border">
            System Status: {online ? 'Online' : 'Backend Unreachable'}
          </div>
        </div>
      </header>

      {actionError && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-800 text-sm p-3 rounded">
          {actionError}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {invoices.map((invoice) => {
          const riskScore = Number(invoice.risk_score) || 0
          const total = parseFloat(invoice.total_amount)
          const flags = Array.isArray(invoice.system_flags) ? invoice.system_flags : []
          const awaitingHuman = ['flagged_for_human_review', 'payout_failed'].includes(invoice.status)
          const busy = busyId === invoice._id

          return (
            <div key={invoice._id} className="bg-white rounded-lg shadow border border-slate-200 overflow-hidden flex flex-col">
              {/* Card Header */}
              <div className="p-5 border-b bg-slate-50 flex justify-between items-start">
                <div>
                  <h2 className="text-lg font-bold text-slate-800">{invoice.vendor_name || 'Unknown vendor'}</h2>
                  <p className="text-sm text-slate-500 font-mono">INV: {invoice.invoice_number || 'N/A'}</p>
                </div>
                <div className="text-right">
                  <p className="text-xl font-bold text-slate-900">${Number.isFinite(total) ? total.toFixed(2) : '0.00'}</p>
                </div>
              </div>

              {/* AI Risk Assessment Section */}
              <div className="p-5 flex-grow">
                <div className="mb-4">
                  <p className="text-xs uppercase font-bold tracking-wider text-slate-400 mb-1">AI Risk Assessment</p>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                      riskScore >= 50 ? 'bg-red-100 text-red-700' :
                      riskScore > 0 ? 'bg-yellow-100 text-yellow-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      Score: {riskScore} / 100
                    </span>
                    <span className="text-sm text-slate-600 uppercase font-semibold">
                      {formatStatus(invoice.status)}
                    </span>
                  </div>
                </div>

                {riskScore > 0 && (
                  <div className="bg-red-50 border border-red-100 p-3 rounded text-sm text-red-800 mb-4">
                    <strong>Warning:</strong> {invoice.risk_explanation}
                    {flags.length > 0 && (
                      <ul className="list-disc pl-5 mt-2 text-xs text-red-700">
                        {flags.map((flag, index) => (
                          <li key={index}>{flag}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {invoice.status === 'payout_failed' && invoice.error && (
                  <p className="text-xs text-red-700 mb-2">Payout error: {invoice.error}</p>
                )}
              </div>

              {/* Human-in-the-Loop Actions */}
              {awaitingHuman && (
                <div className="p-5 border-t bg-slate-50 flex gap-3">
                  <button
                    disabled={busy}
                    onClick={() => runAction(invoice._id, 'reject')}
                    className="flex-1 py-2 bg-white border border-slate-300 rounded text-slate-700 font-semibold hover:bg-slate-50 transition disabled:opacity-50"
                  >
                    Reject
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => runAction(invoice._id, 'approve')}
                    className="flex-1 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700 transition shadow-sm disabled:opacity-50"
                  >
                    {busy ? 'Working...' : 'Approve & Pay'}
                  </button>
                </div>
              )}
            </div>
          )
        })}
        {invoices.length === 0 && (
          <div className="col-span-full text-center p-12 text-slate-500">
            No invoices ingested yet. Upload a PDF to begin.
          </div>
        )}
      </div>
    </div>
  )
}

export default App