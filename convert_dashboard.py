#!/usr/bin/env python3
import json

# Read the dashboard HTML file
with open('dashboard_new.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# Read portfolio data
with open('portfolio_data_enhanced.json', 'r', encoding='utf-8') as f:
    portfolio_data = json.load(f)

# Extract different parts
import re

# Extract styles
style_match = re.search(r'<style>(.*?)</style>', html_content, re.DOTALL)
styles = style_match.group(1) if style_match else ''

# Extract body content
body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL)
body_content = body_match.group(1) if body_match else ''

# Extract scripts
script_matches = re.findall(r'<script>(.*?)</script>', html_content, re.DOTALL)
scripts = '\n'.join(script_matches)

# Create the React component
react_component = f"""'use client'

import {{ useEffect }} from 'react'
import Script from 'next/script'

const portfolioData = {json.dumps(portfolio_data, indent=2)}

export default function FullDashboard() {{
  useEffect(() => {{
    // Initialize portfolio data
    window.portfolioData = portfolioData
    
    // Initialize the dashboard
    if (typeof window.initializeDashboard === 'function') {{
      window.initializeDashboard()
    }}
  }}, [])

  return (
    <>
      <Script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js" />
      <style dangerouslySetInnerHTML={{ __html: `{styles}` }} />
      <div dangerouslySetInnerHTML={{ __html: `{body_content}` }} />
      <script dangerouslySetInnerHTML={{ __html: `
        window.portfolioData = {json.dumps(portfolio_data)};
        {scripts}
      ` }} />
    </>
  )
}}
"""

# Write the component
with open('ib-frontend-clean/src/components/FullDashboard.tsx', 'w', encoding='utf-8') as f:
    f.write(react_component)

print("Dashboard converted successfully!")