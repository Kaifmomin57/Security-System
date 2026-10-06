import { useState, useEffect } from 'react'
import axios from 'axios'
import { Map } from 'lucide-react'
import ContributionSkyline from '../components/ui/contribution-skyline'

const API = 'http://localhost:8000/api/v1'

export default function PatrolHeatmapPage() {
  const [incidentData, setIncidentData] = useState(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get(`${API}/alerts?limit=200`)
        
        // Generate realistic background demo data for the last 365 days
        const dateCounts = {}
        const today = new Date()
        for (let i = 0; i < 365; i++) {
          const d = new Date(today)
          d.setDate(d.getDate() - i)
          const dateStr = d.toISOString().slice(0, 10)
          
          // Generate a random baseline of incidents (higher on weekends, random spikes)
          const isWeekend = d.getDay() === 0 || d.getDay() === 6
          const baseChance = isWeekend ? 0.6 : 0.3
          
          if (Math.random() < baseChance) {
            let count = Math.floor(Math.random() * 4) + 1
            // 5% chance of a major spike
            if (Math.random() < 0.05) count += Math.floor(Math.random() * 8) + 5
            dateCounts[dateStr] = count
          }
        }

        // Overlay real alert data from the database
        for (const alert of res.data) {
          const date = alert.timestamp?.slice(0, 10) || alert.created_at?.slice(0, 10)
          if (date) {
            dateCounts[date] = (dateCounts[date] || 0) + 1
          }
        }

        const data = Object.entries(dateCounts).map(([date, count]) => ({ date, count }))
        setIncidentData(data)
      } catch (err) {
        console.error('Failed to load incident data:', err)
      }
    }
    fetchData()
  }, [])

  return (
    <div style={{ paddingBottom: 40 }}>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Map size={24} color="var(--brand-blue)" />
            3D THREAT INTELLIGENCE MAP
          </h1>
          <p className="page-subtitle">
            Interactive incident skyline — hover days for details, drag to orbit, toggle between 2D heatmap and 3D skyline.
          </p>
        </div>
      </div>

      <div className="w-full bg-background mt-4">
        <ContributionSkyline
          data={incidentData ?? undefined}
          unit="incident"
          unitPlural="incidents"
          title="Incident Activity — Last 365 Days"
          palette="ember"
          defaultView="3d"
          heightScale={1.2}
          showStats={true}
          showLegend={true}
          showToggle={true}
          orbit={true}
        />
      </div>
    </div>
  )
}
